#!/usr/bin/env python
#
# This file is derivied from the Tornado tutorial 
# https://github.com/tornadoweb/tornado/tree/stable/demos/blog and has
# been modified by Yang D.Y. <minvacai@sina.com> for: 
# TextListHandler / AboutHandler/ RawTextHandler/ WordSegHandler and
# relative parts such as template files.
#


#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import bcrypt
import concurrent.futures
import pymongo
import markdown
import os.path
import re
import tornado.escape
from tornado import gen
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import unicodedata
from tornado.options import define, options
import datetime
from bson.objectid import ObjectId
import json

import sys
sys.path.append('./')

define("port", default=9999, help="run on the given port", type=int)

# A thread pool to be used for password hashing with bcrypt.
executor = concurrent.futures.ThreadPoolExecutor(2)

class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/archive", ArchiveHandler),
            (r"/feed", FeedHandler),
            (r"/entry/([^/]+)", EntryHandler),
            (r"/compose", ComposeHandler),
            (r"/auth/create", AuthCreateHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),

            (r"/about", AboutHandler),
            (r"/texts", TextListHandler),
            (r"/raw/([^/]+)", RawTextHandler),
            (r"/ws/([^/]+)", WordSegHandler),
            (r"/export", ExportHandler),
        ]
        settings = dict(
            blog_title=u"分词校对",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__EEEEEEEEEER",
            login_url="/auth/login",
            debug=True
        )
        super(Application, self).__init__(handlers, **settings)
        client = pymongo.MongoClient("mongodb://localhost")
        self.db = client.rawtext


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    def get_current_user(self):
        user_id = self.get_secure_cookie("rawtext_user")

        if not user_id:
            return None
        usernm = "".join([chr(x) for x in user_id])
        user = self.application.db.authors.find_one({'name': usernm})
        return user

    def any_author_exists(self):
        one = self.db.authors.find_one()
        return bool(one)


class HomeHandler(BaseHandler):
    def get(self):
        entries =[]
        cursor = self.db.entries.find().limit(5)
        for entry in cursor:
            entries.append(entry)
        self.render("home.html", entries=entries)


class EntryHandler(BaseHandler):
    def get(self, slug):
        entry = self.db.entries.find_one({"slug": slug})
        if not entry: raise tornado.web.HTTPError(404)
        self.render("entry.html", entry=entry)


class ArchiveHandler(BaseHandler):
    def get(self):
        cursor = self.db.entries.find().sort('published', -1)
        entries = [entry for entry in cursor]
        self.render("archive.html", entries=entries)


class FeedHandler(BaseHandler):
    def get(self):
        entries = []
        cursor = self.db.entries.find().sort('published', -1).limit(10)
        for entry in cursor:
            entries.append(entry)
        self.set_header("Content-Type", "application/atom+xml")
        self.render("feed.xml", entries=entries)


class ComposeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        article_id = self.get_argument("id", None)
        entry = None
        if article_id:
            entry = self.db.entries.find_one({"_id": ObjectId(article_id)})
        self.render("compose.html", entry=entry)

    @tornado.web.authenticated
    def post(self):
        id = self.get_argument("_id", None)
        title = self.get_argument("title")
        text = self.get_argument("markdown")
        html = markdown.markdown(text)
        # if user_name:
        if id:
            entry = self.db.entries.find_one({"_id": ObjectId(id)})
            if not entry: raise tornado.web.HTTPError(404)
            slug = entry["slug"]
            doc = {
                "title": title,
                "markdown": text,
                "html": html,
                "last_modify":datetime.datetime.utcnow()
            }
            self.db.entries.update_one({"_id": ObjectId(id)}, {"$set": doc})

        else:
            slug = str(unicodedata.normalize("NFKD", title).encode(
                "ascii", "ignore"))
            slug = re.sub(r"[^\w]+", " ", str(slug))
            slug = "-".join(slug.lower().strip().split())
            if not slug: slug = "entry"
            while True:
                e = self.db.entries.find_one({"slug": slug})
                if not e: break
                slug += "-2"
            doc = {
                "author_id": str(self.current_user["_id"]),
                "author_name": self.current_user["name"],
                "title": title,
                "slug": slug,
                "markdown": text,
                "html": html,
                "published": datetime.datetime.utcnow()
            }
            self.db.entries.insert_one(doc)
        self.redirect("/entry/" + slug)


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_author.html")

    @gen.coroutine
    def post(self):
        if self.any_author_exists():
            raise tornado.web.HTTPError(400, "author already created")
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt())
        author = {
            "email": self.get_argument("email"),
            "name": self.get_argument("name"),
            "hashed_password": hashed_password
        }
        try:
            result = self.db.authors.insert_one(author)
        except Exception as e:
            raise tornado.web.HTTPError(404)
        self.set_secure_cookie("rawtext_user", author["name"])
        self.redirect(self.get_argument("next", "/"))


class AuthLoginHandler(BaseHandler):
    def get(self):
        # If there are no authors, redirect to the account creation page.
        if not self.any_author_exists():
            self.redirect("/auth/create")
        else:
            self.render("login.html", error=None)

    @gen.coroutine
    def post(self):
        author = self.db.authors.find_one({'email': self.get_argument("email")})
        if not author:
            self.render("login.html", error="email not found")
            return
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(author["hashed_password"]))
        if hashed_password == author["hashed_password"]:
            self.set_secure_cookie("rawtext_user", author["name"])
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="incorrect password")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("rawtext_user")
        self.redirect(self.get_argument("next", "/"))


class EntryModule(tornado.web.UIModule):
    def render(self, entry):
        return self.render_string("modules/entry.html", entry=entry)


class TextListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = self.get_argument("page", None)
        num = self.get_argument("num", None)
        status = self.get_argument("type", None)
        statuslst = ['raw', 'cut', 'check']
        query = {}
        if status:
            # 卧槽，忘记为什么要这样写了
            if status in '123':
                query = {'status':statuslst[int(type)]}
        if not num:
            num = 20
        if not page:
            page = 0
        else:
            page = int(page)
        cursor = self.db.text.find(
            query,
            {
                '_id': 1,
                'batch': 1,
                'summary': 1,
                'info': 1,
                'status': 1,
                'creator': 1,
                'create_time': 1
            }
        ).sort("create_time", -1).skip(page * num).limit(num)
        raws = []
        status_table = ["已删除", "未处理", "已分词", "已校对"]
        for raw in cursor:
            raw["_id"] = str(raw["_id"])
            raw["info"]["source"] = raw["info"]["source"][:10]
            raw["info"]["author"] = raw["info"]["author"][:10]
            raw["info"]["url"] = raw["info"]["url"][:10]
            raw["status"] = status_table[raw["status"]]
            raw["summary"] = raw["summary"][:10] + "..."

            #raw["creator"] = self.get_current_user()    #str(raw["creator"])
            raws.append(raw)
        # print("raws: ", raws)
        self.render("textlist.html", raws=raws, page=page)


class AboutHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        text = {
            'title': "一些说明",
            'author': "redsky",
            'content': [
                "写得很乱，应该用Backbone的，大意了！"
            ],
            'date': '2017/5/22 12:18'
        }
        self.render("about.html", texts=text)


class RawTextHandler(BaseHandler):
    """
    add/modify raw text; cut/check not here.
    text status: 
    """
    @tornado.web.authenticated
    def get(self, id):
        text = []
        # id = self.get_argument("id", None)
        if id:
            text = self.db.text.find_one({"_id": ObjectId(id)})
            text["_id"] = str(text["_id"])
        self.render("text.html", text=text, msg="")

    @tornado.web.authenticated
    def post(self):
        id = self.get_argument("_id", None)
        whitelst = [
            'batch',
            'raw'
        ]
        infolst = [
            'source',
            'author',
            'field',
            'time'
        ]
        error_flag = False
        doc = {'info': {}}
        for item in whitelst:
            doc[item] = self.get_argument(item, None)
            if not doc[item]:
                error_flag = True
                break
        for item in infolst:
            doc["info"][item] = self.get_argument(item)
            if not doc["info"][item]:
                error_flag = True
                break
        if error_flag:
            self.render("text.html", error="请填写所有项！")
            return
        doc['info']['field'] = doc['info']['field'].split(',')
        source_url = self.get_argument('url', None)
        if source_url:
            doc["info"]['url'] = source_url
        doc['summary'] = doc['raw'][:40] + "..."
        creator_info = self.get_current_user()
        creator = {
            'name': creator_info['name'],
            'email': creator_info['email']
        }
        doc['creator'] = creator

        print("id: ", id)
        if id:
            doc['modify_time'] = datetime.datetime.utcnow()
            self.db.text.update_one({"_id": ObjectId(id)}, {"$set": doc})
        else:
            doc['create_time'] = datetime.datetime.utcnow()
            doc['status'] = 1
            self.db.text.insert_one(doc)
        self.redirect("/texts")

class WordSegHandler(BaseHandler):
    """
    add/modify raw text; cut/check not here.
    text status:
    """
    @tornado.web.authenticated
    def get(self, id):
        text = []
        # id = self.get_argument("id", None)
        if id:
            text = self.db.text.find_one(
                {"_id": ObjectId(id)},
                {
                    "_id": 1,
                    "raw": 1,
                    "proofreaded": 1,
                    "cut": 1
                }
            )

            text["_id"] = str(text["_id"])
        else:
            self.redirect("/texts/")
            # self.render("wslist.html", result=text["proofreaded"], id=text["_id"])
            return
        if "proofreaded" in text:   #text["proofreaded"]:
            data = text["proofreaded"]
        else:
            data = text["cut"]
        self.render(
            "wordseg.html",
            result=data,
            raw=text["raw"],
            id=id,
            error=""
        )

    @tornado.web.authenticated
    def post(self, id):
        # id = self.get_argument("_id", None)
        data = self.get_argument("data", None)
        proofreaded = self.get_argument("proofreaded_ok", None)
        # json to dict
        if not data:
            return
        try:
            wordlst = json.loads(data)
        except Exception as e:
            return

        # find document from MongoDB by id, verify wether data string equals to raw or cut
        text = self.db.text.find_one(
            {
                "_id": ObjectId(id)
            },
            {
                "_id": 1,
                "raw": 1,
                "cut": 1
            }
        )
        if not text:
            self.redirect("/texts/")
            return
        if "cut" not in text:
            self.redirect("/texts/")
            return
        # compare data
        input_str = "".join(wordlst)
        orgin_str = "".join(text["cut"])
        if input_str != orgin_str:
            self.render(
                "wordseg.html",
                result=text["cut"],
                id=id,
                raw="",
                error="与原始数据不吻合！"
            )
            return

        # update document in MongoDB by id
        values = {
            "$set":
                {
                    "proofreaded": wordlst,
                }
        }
        if proofreaded:
            values["$set"]["status"] = 3
        rvalue = self.db.text.update_one(
            {
                "_id": ObjectId(id)
            },
            values
        )
        if rvalue:
            self.render(
                "wordseg.html",
                result=wordlst,
                id=id,
                raw=text["raw"],
                error=""
            )
        else:
            self.render(
                "wordseg.html",
                result=[],
                id=id,
                raw="",
                error="更新数据失败！"
            )




class ExportHandler(BaseHandler):
    """
    select data and export
    """
    @tornado.web.authenticated
    def get(self):
        self.render("export.html")

    @tornado.web.authenticated
    def post(self):
        batch_list = self.get_argument("batch")
        if not batch_list:
            self.render("export.html", error=1)
            return

        query = {"status": 3}
        if batch_list != "ALL":
            try:
                batch = [x.strip() for x in batch_list.split(",")]
                query["batch"] = {"$in": batch}
            except Exception as e:
                self.render("export.html", error="参数有误")
                return
        filter = {"_id":0, "proofreaded": 1}
        cursor = self.db.text.find( query, filter )
        lst = []

        for ele in cursor:
            for word in ele["proofreaded"]:
                length = len(word)
                if length == 1:
                    lst.append(word[0] + '/s')
                else:
                    lst.append(word[0] + '/b')
                    for c in word[1:-1]:
                        lst.append(c + '/m')
                    lst.append(word[-1] + '/e')
            lst.append('\n/s')
        train = ' '.join(lst)
        filenm = 'train_{0}'.format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        self.set_header('Content-Type', 'application/octet-stream')
        self.set_header('Content-Disposition', 'attachment; filename=' + filenm)
        buf_size = 4096
        count = 0
        while True:
            data = train[count:count+buf_size]
            self.write(data)
            if count + buf_size > len(train):
                break
            count += buf_size
        self.finish()




def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
