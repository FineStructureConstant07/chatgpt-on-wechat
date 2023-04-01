import emoji

def delelem(data):
    """
    删除多余的标点符号   出现的无用空格   不出现中文字符的数据行
    :param data: list
    :return: list
    """
    res_del = []

    for i in data:
        # 使用空字符替换掉间隔符
        a = re.sub(r'\s', '', i)

        # 使用精准匹配，匹配连续出现的符号;并用空字符替换他
        b = re.sub(r'\W{2,}', '', a)

        # 使用空字符替换空格
        c = re.sub(r' ', ' ', b)

        # 删除没有中文的数据行
        if len(re.findall(r"[\u4e00-\u9fa5]", c)) >= 3:
            res_del.append(c)

    return res_del 

def textClaiming(data)
    res = emoji.replace_emoji(data, replace="**")
    res = delelem(res)
    res = strQ2B(res)

    return res


def strQ2B(ustring):
    """全角转半角"""
    rstring = ""
    for uchar in ustring:
        inside_code=ord(uchar)
        if inside_code == 12288:                              #全角空格直接转换            
            inside_code = 32 
        elif (inside_code >= 65281 and inside_code <= 65374): #全角字符（除空格）根据关系转化
            inside_code -= 65248

        rstring += unichr(inside_code)
    return rstring

