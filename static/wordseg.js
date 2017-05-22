function randColor(flag){
  var charTable = ["D0", "F0"];
  var color = "#";
  for(var i=0;i<3;i++){
    color = color + charTable[Math.floor(Math.random()*2)];
  }
  return color;
}

function changeStyle(){
  var new_color = "";
  var old_color = "";
  var list = document.getElementsByClassName("word");
  for(var i=0;i<list.length;i++){
    while(new_color == old_color) new_color = randColor(i);
    list[i].style.background = new_color;
    old_color = new_color;
  }
}

function checkRadios(){
    var status;

    var arr=document.getElementsByName("optionsRadios");
    for(var i=0;i<arr.length;i++){
        if(arr[i].checked){
            status = arr[i].value;
        }
    }
    return status;
}

function pickWord(index, word){
    var status = checkRadios();
    switch(status){
        case "new":
        case "modify":
        case "del":
            $("#word_id").val(index);
            $("#word_text").val(word);
        break;

        case "combine":
            var tmp_word = word.replace(/\<br info="换行"\/\>/g, '&lt;br info="换行"\/&gt;');
            add2Lst(index,tmp_word);
        break;

        default:
        break;
    }
}

function removeListEle(index){
    var child = document.getElementById(index);
    child.remove();
}

function clearLst(){
    var s=document.getElementById('combine_lst');
    var total=s.childNodes.length;
    for (var i=total-1;i>=0;i--){
        s.removeChild(s.childNodes[i]);
    }
}

function clearBoxes(){
    var id_box = document.getElementById('word_id');
    var text_box = document.getElementById('word_text');
    id_box.value = ""
    text_box.value = ""
}

function cleanAll(){
    clearLst();
    clearBoxes();
}

function checkDataBox(){
    var id_box = document.getElementById('word_id');
    var text_box = document.getElementById('word_text');
    var id_flag = 0;
    var text_flag = 0;

    if (id_box.value != "") id_flag = 10;
    if (text_box.value != "") text_flag = 1;
    return id_flag + text_flag;
}

function add2Lst(index, word){
    // Append index+1 to combile-list if the list is not empty
    var tid = Date.parse( new Date());
    var combine_lst=document.getElementById('combine_lst');
    var children = combine_lst.childNodes;

    if(combine_lst.childNodes.length > 0){
        // 获取列表中最后一个元素的索引
        var lst = getWordsFromPage();
        var last = children[children.length -1].childNodes[0].childNodes[0].innerHTML;
        var n = parseInt(last) + 1;
        index = n;
        word = lst[n];
    }
    var tr= document.createElement("tr");
    var tr_index = tid + index + Math.random();

    var htmltext = "<td><span>" + index + "</span></td>";
    htmltext += "<td><span>" +word+ "</span></td>";
    htmltext += "<td><button class=\"btn btn-default\" onclick='removeListEle(\"" + tr_index +"\");'>删除</button></td>";
    tr.innerHTML=htmltext;

    tr.setAttribute("id", tr_index);
    tr.setAttribute("value", index);
    tr.setAttribute("class", "c_lst");
    combine_lst.appendChild(tr);
}


// get data from input-box or combine-word-list
function changeWordList(){
    var i, index;
    var pos, word;
    var words = getWordsFromPage();
    var status = checkRadios();
    var word = "";
    var new_word_len = 0;
    if(status != "combine"){
        // get data from 2 input boxes
        pos = document.getElementById("word_id").value;
        if(typeof pos === "string"){
            index = parseInt(pos);
            if(index >= words.lengh){
                alert("索引搞错了吧……");
                return words;
            }
        }
        word = document.getElementById("word_text").value;
    }else{
        // 从合并表中获取数据
        var root = document.getElementById('combine_lst');
        var children = root.childNodes;
        var grand_children;
        pos = children[0].getAttribute("value");
        index = parseInt(pos);

        new_word_len = children.length;
        for(i=0; i < new_word_len; i++){
            grand_children = children[i].childNodes;
            word += grand_children[1].childNodes[0].innerHTML;
        }
    }

    // 插入、删除、更改某个词
    var flag = 0;
    switch(status){
        case "new":
            flag = checkDataBox();
            if(flag != 11){
                alert("请填写待创建新词的位置及文本！");
                return;
            }
            words.splice(index, 0, word);
        break;

        case "modify":
            flag = checkDataBox();
            if(flag != 11){
                alert("请填写待修改词的位置及文本！");
                return;
            }
            words[index] = word;
        break;

        case "combine":
            words.splice(index, new_word_len, word);
        break;

        case "del":
            flag = checkDataBox();
            if(flag <10){
                alert("请填写待删除词的位置！");
                return;
            }
            var rvalue = confirm("确定要删除 " +index+ " 处的词 [" +words[index]+ "]？");
            if(rvalue){
                words.splice(index, 1);
            }
        break;

        default:
        break;
    }
    cleanAll();
    renewLst(words);

    var radioEle = document.getElementById('radio_modify');
    radioEle.checked=true;
    return words;
}

function renewLst(words){
    // renew word-list from array to web page
    var i;
    var root = document.getElementById('words_containor');
    var total=root.childNodes.length;
    var child = root.childNodes;
    for (i=total-1;i>=0;i--){
        child[i].remove();
    }
    var span_str, span;
    var tmp_word;
    //重新添加
    for(i=0; i<words.length; i++){
        span = document.createElement("span");
        span.setAttribute("class", "word");
        span.setAttribute("title", i);
        tmp_word = words[i].replace(/(?:\r\n|\r|\n)/g, '<br info="换行">');
        span.setAttribute("onclick", "pickWord('" + i + "', '" + tmp_word + "');");
        span.innerHTML = tmp_word;
        root.appendChild(span);
    }
    // 将数据加入到datafield
    var dataEle = document.getElementById('datafield');
    dataEle.setAttribute("value", createData())
    changeStyle();
}

function createData(){
    // 整理分词列表格式，准备提交到服务器
    var wordlst = getWordsFromPage();
    for(i=0; i<wordlst.length; i++){
        wordlst[i] = wordlst[i].replace(/<br info="换行">/g, '\n');
    }
    data = JSON.stringify(wordlst);
    return data;
}

function getWordsFromPage(){
    // get word-list from current web page
    var list = document.getElementsByClassName("word");  //words_containor
    var words = [];
    var child = list;//.childNodes;

    for(var i=0;i<child.length;i++){
        words.push(child[i].innerHTML);
    }
    return words;
}

function debugShowList(){
    var wordlist = getWordsFromPage();
    var debug_box = document.getElementById('debug_box');
    debug_box.innerHTML = wordlist.join(" ");
}