# encoding:utf-8

"""
wechat channel
"""

import itchat
import json
from itchat.content import *
from channel.channel import Channel
from concurrent.futures import ThreadPoolExecutor
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf
import requests
import io
from datetime import datetime
import os                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  


# Set up temporary file to store group messages
temp_file = "group_messages.txt"
# Define maximum number of group messages to save before sending to bot
max_group_messages = 1800 

thread_pool = ThreadPoolExecutor(max_workers=8)


@itchat.msg_register(TEXT)
def handler_single_msg(msg):
    WechatChannel().handle_text(msg)
    return None


@itchat.msg_register(TEXT, isGroupChat=True)
def handler_group_msg(msg):
    WechatChannel().handle_group(msg)
    return None


@itchat.msg_register(VOICE)
def handler_single_voice(msg):
    WechatChannel().handle_voice(msg)
    return None


class WechatChannel(Channel):
    def __init__(self):
        pass

    def startup(self):
        # login by scan QRCode
        itchat.auto_login(enableCmdQR=2)

        # start message listener
        itchat.run()

    def handle_voice(self, msg):
        if conf().get('speech_recognition') != True :
            return
        logger.debug("[WX]receive voice msg: " + msg['FileName'])
        thread_pool.submit(self._do_handle_voice, msg)

    def _do_handle_voice(self, msg):
        from_user_id = msg['FromUserName']
        other_user_id = msg['User']['UserName']
        if from_user_id == other_user_id:
            file_name = TmpDir().path() + msg['FileName']
            msg.download(file_name)
            query = super().build_voice_to_text(file_name)
            if conf().get('voice_reply_voice'):
                self._do_send_voice(query, from_user_id)
            else:
                self._do_send_text(query, from_user_id)

    def handle_text(self, msg):
        logger.debug("[WX]receive text msg 000: " + json.dumps(msg, ensure_ascii=False))
        content = msg['Text']
        self._handle_single_msg(msg, content)

    def _handle_single_msg(self, msg, content):
        from_user_id = msg['FromUserName']
        to_user_id = msg['ToUserName']              # 接收人id
        other_user_id = msg['User']['UserName']     # 对手方id
        match_prefix = self.check_prefix(content, conf().get('single_chat_prefix'))
        if "」\n- - - - - - - - - - - - - - -" in content:
            logger.debug("[WX]reference query skipped")
            return
        if from_user_id == other_user_id and match_prefix is not None:
            # 好友向自己发送消息
            if match_prefix != '':
                str_list = content.split(match_prefix, 1)
                if len(str_list) == 2:
                    content = str_list[1].strip()

            img_match_prefix = self.check_prefix(content, conf().get('image_create_prefix'))
            if img_match_prefix:
                content = content.split(img_match_prefix, 1)[1].strip()
                thread_pool.submit(self._do_send_img, content, from_user_id)
            else :
                thread_pool.submit(self._do_send_text, content, from_user_id)
        elif to_user_id == other_user_id and match_prefix:
            # 自己给好友发送消息
            str_list = content.split(match_prefix, 1)
            if len(str_list) == 2:
                content = str_list[1].strip()
            img_match_prefix = self.check_prefix(content, conf().get('image_create_prefix'))
            if img_match_prefix:
                content = content.split(img_match_prefix, 1)[1].strip()
                thread_pool.submit(self._do_send_img, content, to_user_id)
            else:
                thread_pool.submit(self._do_send_text, content, to_user_id)


    def handle_group(self, msg):
        logger.debug("[WX]receive group msg 00000: " + json.dumps(msg, ensure_ascii=False))
        group_name = msg['User'].get('NickName', None)
        group_id = msg['User'].get('UserName', None)
        logger.debug("[WX]handle_group {}".format(group_name)) 
        if not group_name:
            return ""
        origin_content = msg['Content']
        content = msg['Content']
        content_list = content.split(' ', 1)
        context_special_list = content.split('\u2005', 1)
        if len(context_special_list) == 2:
            content = context_special_list[1]
        elif len(content_list) == 2:
            content = content_list[1]
        if "」\n- - - - - - - - - - - - - - -" in content:
            logger.debug("[WX]reference query skipped") 
            return ""
        config = conf()
        match_prefix = (msg['IsAt'] and not config.get("group_at_off", False)) or self.check_prefix(origin_content, config.get('group_chat_prefix')) is not None \
                       or self.check_contain(origin_content, config.get('group_chat_keyword'))
        logger.debug("[WX]handle_group match_prefix {} {} ".format(match_prefix, msg['IsAt'] )) 
        logger.debug("[WX]handle_group match_prefix {} {} ".format(self.check_prefix(origin_content, config.get('group_chat_prefix')), origin_content)) 
        logger.debug("[WX]handle_group match_prefix {} {} ".format((msg['IsAt'] and not config.get("group_at_off", False)), config.get("group_at_off", False))) 
        if ('ALL_GROUP' in config.get('group_name_white_list') or group_name in config.get('group_name_white_list') or self.check_contain(group_name, config.get('group_name_keyword_white_list'))) and match_prefix:
            img_match_prefix = self.check_prefix(content, conf().get('image_create_prefix'))
            if img_match_prefix:
                content = content.split(img_match_prefix, 1)[1].strip()
                # thread_pool.submit(self._do_send_img, content, group_id)
            else:
                thread_pool.submit(self._do_send_group, content, msg)
                logger.debug("[WX]handle_group content {}".format(content)) 

    def send(self, msg, receiver):
        itchat.send(msg, toUserName=receiver)
        logger.info('[WX] sendMsg={}, receiver={}'.format(msg, receiver))

    def _do_send_voice(self, query, reply_user_id):
        try:
            if not query:
                return
            context = dict()
            context['from_user_id'] = reply_user_id
            reply_text = super().build_reply_content(query, context)
            if reply_text:
                replyFile = super().build_text_to_voice(reply_text)
                itchat.send_file(replyFile, toUserName=reply_user_id)
                logger.info('[WX] sendFile={}, receiver={}'.format(replyFile, reply_user_id))
        except Exception as e:
            logger.exception(e)

    def _do_send_text(self, query, reply_user_id):
        try:
            if not query:
                return
            context = dict()
            context['session_id'] = reply_user_id
            reply_text = super().build_reply_content(query, context)
            if reply_text:
                self.send(conf().get("single_chat_reply_prefix") + reply_text, reply_user_id)
        except Exception as e:
            logger.exception(e)

    def _do_send_img(self, query, reply_user_id):
        try:
            if not query:
                return
            context = dict()
            context['type'] = 'IMAGE_CREATE'
            img_url = super().build_reply_content(query, context)
            if not img_url:
                return

            # 图片下载
            pic_res = requests.get(img_url, stream=True)
            image_storage = io.BytesIO()
            for block in pic_res.iter_content(1024):
                image_storage.write(block)
            image_storage.seek(0)

            # 图片发送
            itchat.send_image(image_storage, reply_user_id)
            logger.info('[WX] sendImage, receiver={}'.format(reply_user_id))
        except Exception as e:
            logger.exception(e)

    def _do_send_group(self, query, msg):
        logger.info('[WX] _do_send_group query {} '.format(query))
        if not query:
            return 
        context = dict()
        group_name = msg['User']['NickName']
        group_id = msg['User']['UserName']
        group_chat_in_one_session = conf().get('group_chat_in_one_session', [])
        if ('ALL_GROUP' in group_chat_in_one_session or \
                group_name in group_chat_in_one_session or \
                self.check_contain(group_name, group_chat_in_one_session)):
            context['session_id'] = group_id
            query = self._save_msg_group(query, msg)
            logger.info('[WX] _do_send_group get query {} '.format(query))
            if not query:
                return
        else:
            context['session_id'] = msg['ActualUserName']
        reply_text = super().build_reply_content(query, context)
        if reply_text:
            reply_text = '@' + msg['ActualNickName'] + ' ' + reply_text.strip()
            #self.send(conf().get("group_chat_reply_prefix", "") + reply_text, group_id)
            itchat.send(group_name + reply_text, toUserName='filehelper')

        
    def _save_msg_group(self, query, msg):
        try:
            all_msgs = ""
            now = datetime.now()  # 获取当前时间
            logger.info('[WX] _save_msg_group query {} '.format(query))

            temp_group_file = msg['User']['NickName'] + temp_file;
            if not os.path.exists(temp_group_file):
                with open(temp_group_file, 'w') as f:
                    pass
            
            with open(temp_group_file, 'a+') as f:
                f.write('[' + now.strftime("%M:%S") + '][ ' + msg['ActualNickName'] + ']: ' + query + '\n')
                logger.info('[WX] saveFile query {} line {}'.format(query, f.tell()))
                if f.tell() > max_group_messages:
                    f.seek(0)
                    all_msgs = f.read().strip()
                    f.seek(0)
                    f.truncate()
                    logger.info('[WX] getFile query {} line {}'.format(all_msgs, f.tell()))
                     
                    all_msgs = "请问，我有一些聊天记录，格式是  [时间] [昵称]：内容 。 \n 你能帮我总结一下主要话题吗？ 请给出综述，谢谢 \n 之后请分别归类主要话题，同时统计出涉及某个话题的记录个数，给出这个话题的总结综述，和重点汇总摘要。 \n 需要特别字体显示 关于 新冠，流感，疫情，防护，购买 的话题 ，以及别的你���为重要的别的话题。  \n 在回答的最后请帮忙统计总的记录个数，和本次对话消耗的Token个数。 \n 谢谢  \n 如下是记录： \n "  + all_msgs 
                    return all_msgs
            

            logger.info('[WX] _save_msg_group file query list {} '.format(f))                                
    





        except Exception as e:
            logger.exception(e)
        
    def check_prefix(self, content, prefix_list):
        for prefix in prefix_list:
            if content.startswith(prefix):
                return prefix
        return None


    
    def check_contain(self, content, keyword_list):
        if not keyword_list:
            return None
        for ky in keyword_list:
            if content.find(ky) != -1:
                return True
        return None
    