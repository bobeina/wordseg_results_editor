# coding=utf8


import re
import numpy as np
import pandas as pd
import h5py
# import datetime
from keras.utils import np_utils
from keras.layers import Dense, Embedding, LSTM, TimeDistributed, Input, Bidirectional
from keras.models import Model


class WordSeq():
    """
    这个分词程序根据苏剑林的算法修改而来；训练部分太乱，目前暂时懒得重构，就先不放上来了……
    需要两个文件：一个训练好的权值，一个已处理过的字的列表；
    另外要实际应用的话，其实还有一些问题有待改进。 - by minvacai@sina.com 2017/5/22
    """
    def __init__(self, old_chars_list_file, weight_file):
        """
        初始化
        :param old_chars_list_file: 待读取的已经处理过的字的列表
        """
        self.old_chars_list_file = old_chars_list_file
        self.maxlen = 48
        self.word_size = 128
        self.total_char = 0
        self.old_chars = None
        self.load_char_lst(old_chars_list_file)
        # 原始的字列表长度
        self.origin_char_num = self.total_char
        self.create_model()

        # 读取权值
        self.load_weights(weight_file)
        self.zy = self.set_transfer_prob()
        print("RNN initialize done.")
        return

    def load_char_lst(self, filenm):
        """
        读取汉字列表
        :param filenm: char list
        :return:
        """
        try:
            self.old_chars = pd.Series.from_csv(filenm, encoding='utf-8')
            # 计算长度
            self.total_char = len(self.old_chars)
        except Exception as e:
            print("Word-cut fail: cannot load file {0}.", filenm)
            raise e

    def scan_new_char(self):
        """
        扫描待切分的文本，扫描出之前未在字列表中的字
        :return:
        """
        # TODO
        return

    def load_weights(self, filenm):
        try:
            print("Loading weight file {0} ... ".format(filenm)),
            file = h5py.File(filenm, 'r')
            weight = []
            for i in range(len(list(file.keys()))):
                weight.append(file['weight' + str(i)][:])
            self.model.set_weights(weight)
            print("done.")
        except Exception as e:
            print("Load weight file %s fail." % (filenm))
            raise e

    def create_model(self):
        print("Create mode..."),
        sequence = Input(shape=(self.maxlen,), dtype='int32')
        embedded = Embedding(len(self.old_chars) + 1,
                             self.word_size,
                             input_length=self.maxlen,
                             mask_zero=True)(sequence)
        blstm = Bidirectional(LSTM(64, return_sequences=True), merge_mode='sum')(embedded)
        output = TimeDistributed(Dense(5, activation='softmax'))(blstm)
        self.model = Model(input=sequence, output=output)
        self.model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
        print("done.")
        return

    def set_transfer_prob(self):
        """
        转移概率，原作者单纯用了等概率
        我统计了一下原语料中的实际概率 - by minvacai@sina.com
        :return:
        """
        zy = {'be': 0.25670099613597036,
              'bm': 0.053124417941731186,
              'eb': 0.14689263644605108,
              'es': 0.16294282477853125,
              'me': 0.05311591650975513,
              'mm': 0.052334815244561725,
              'sb': 0.1628907857100718,
              'ss': 0.11199760723332747
              }
        zy = {i: np.log(zy[i]) for i in list(zy.keys())}
        return zy

    def viterbi(self, nodes):
        paths = {'b': nodes[0]['b'], 's': nodes[0]['s']}
        for l in range(1, len(nodes)):
            paths_ = paths.copy()
            paths = {}
            for i in list(nodes[l].keys()):
                nows = {}
                for j in list(paths_.keys()):
                    if j[-1] + i in list(self.zy.keys()):
                        nows[j + i] = paths_[j] + nodes[l][i] + self.zy[j[-1] + i]
                k = np.argmax(list(nows.values()))
                paths[list(nows)[k]] = list(nows.values())[k]
        return list(paths)[np.argmax(list(paths.values()))]

    def simple_cut(self, s):
        """

        :param s:
        :return:
        """
        if s:
            r = self.model.predict(
                np.array([
                    list(self.old_chars[list(s)].fillna(0).astype(int))+[0]*(self.maxlen-len(s))
                ]),
                verbose=False)[0][:len(s)]
            r = np.log(r)
            nodes = [dict(list(zip(['s','b','m','e'], i[:4]))) for i in r]
            t = self.viterbi(nodes)
            words = []
            for i in range(len(s)):
                if t[i] in ['s', 'b']:
                    words.append(s[i])
                else:
                    words[-1] += s[i]
            return words
        else:
            return []

    def cut_str(self, text, step):
        """
        按定长切割字符串
        :param text: 待切割文本
        :param step: 切割长度
        :return:
        """
        result = []
        begin = 0
        end = len(text)
        for i in range(begin, end, step):
            if i + step < end:
                t_end = i + step
            else:
                t_end = end
            result.append(text[i:t_end])
        return result

    def text_to_words(self, s):
        result = []
        j = 0
        not_cuts = self.cut_str(s, 48)
        for i in not_cuts:
            result.extend(self.simple_cut(i))   # self.simple_cut(i))
        return result

    def run(self, t_text):
        seg = []

        # TODO: 待查看添加生字部分，至少要将未识别字符列表保存下来看一下
        # TODO 将生字加入字表
        # self.scan_new_char(t_text)

        for index, txt in enumerate(t_text):
            c_text = self.text_to_words(txt)
            seg.append(c_text)
        return seg



