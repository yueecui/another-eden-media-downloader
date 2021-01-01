import requests
import random
import re
import threading_danteng
import time
import math
import mwparserfromhell
from hashlib import md5
from danteng_lib import *
from urllib.parse import quote
from collections import OrderedDict


class HuijiWiki(threading_danteng.ObjectDanteng):
    def __init__(self, key, name='', cookies=None, project=None):
        super().__init__()
        self._url = 'https://%s.huijiwiki.com/' % key  # 暂时没用
        self._wiki_url = self._url  # 暂时没用
        self._api_url = self._wiki_url + "api.php"
        self._index_url = self._wiki_url + "index.php"
        self._user_agent = {'user-agent': 'Yuee-Tool/0.1'}
        self._edit_token = None
        self._cookies = None
        self._summary = 'by Yuee_Bot'
        self._project = None
        self._permission_level = 1
        self._permission_high_level_list = ['Yuee bot', 'Yuee_bot']
        self.set_thread_number(10)
        self.set_sleep_time(1)
        self._timeout = 30

        self._log_title = 'WIKI'
        self._key = key
        self._name = name
        self._cookies = cookies
        self._project = project
        self.state_stop = False

        self.result = None
        self._rollback_token = '+\\'

    # 设定描述（编辑页面）/理由（删除/恢复页面）
    def set_summary(self, summary):
        self._summary = summary
        return True

    def _log_output(self, log_str):
        if self._project:
            self._project.log(log_str)
        else:
            super()._log_output(log_str)

    # 登录MEDIAWIKI
    def login(self, user, passwd):
        self._que_in.put({'action': 'login',
                          'lgname': user,
                          'lgpassword': passwd,
                          'nosleep': True,
                          'type': 'params',
                          'update_progress': False})
        t = WikiPoster(self._que_in, self._que_out, self._api_url, self._cookies, self._user_agent)
        t.start()
        t.join()
        result = t.get_result()
        try:
            if result['clientlogin']['status'] == 'PASS':
                self._cookies = result['cookies']
            else:
                print(result['clientlogin']['message'])
        except Exception as e:
            print('登录结果未找到：%s' % e)
        return result

    # 获取灰机永用户信息（ID，头像）
    def get_huijiuserinfo(self):
        params = dict(action=(None, 'query'),
                      meta=(None, 'huijiuserinfo'),
                      uiprop=(None, 'avatar'))
        self._que_in.put({'action': 'huijiuserinfo',
                          'nosleep': True,
                          'type': 'files',
                          'params': params,
                          'update_progress': False})
        t = WikiPoster(self._que_in, self._que_out, self._api_url, self._cookies, self._user_agent)
        t.start()
        t.join()
        result = t.get_result()
        try:
            return result['query']['huijiuserinfo']
        except Exception as e:
            print('获取灰机用户信息失败：%s' % e)
            return False

    # 登录MEDIAWIKI
    def login_bot(self, user, passwd):
        params = dict(action=(None, 'login'),
                      lgname=(None, 'user'),
                      lgpassword=(None, 'passwd'))
        self._que_in.put({'action': 'login_bot',
                          'nosleep': True,
                          'type': 'files',
                          'params': params,
                          'update_progress': False})
        t = WikiPoster(self._que_in, self._que_out, self._api_url, self._cookies, self._user_agent)
        t.start()
        t.join()
        result = t.get_result()
        try:
            if result['login']['result'] == 'Success':
                self._cookies = result['cookies']
        except Exception as e:
            print('登录结果未找到：%s' % e)
        return result

    def is_login(self):
        return True if self._cookies else False

    def check_usergroups(self):
        params = {'action': 'query',
                  'meta': 'userinfo',
                  'uiprop': 'groups'}
        self._que_in.put({'action': 'check_usergroups',
                          'nosleep': True,
                          'type': 'params',
                          'params': params,
                          'update_progress': False})
        t = WikiPoster(self._que_in, self._que_out, self._api_url, self._cookies, self._user_agent)
        t.start()
        t.join()
        result = t.get_result()
        print(result)
        try:
            groups = result['query']['userinfo']['groups']
            # staff账号可以使用
            if 'staff' in groups or 'bot-global' in groups:
                self._permission_level = 999
                return 999
            # 普通用户必须同时拥有机器人和（管理员或是行政员）权限
            if 'bot' in groups:
                for g in ['sysop', 'bureaucrat', 'staff', 'sysop-global']:
                    if g in groups:
                        # print('用户是管理员 / 行政员。')
                        if result['query']['userinfo']['name'] in self._permission_high_level_list:
                            self._permission_level = 311
                            return 311
                        else:
                            self._permission_level = 1
                            return 1
                return -2
            return -1
        except:
            # print(result)
            return -1000

    # 获得编辑令牌
    def get_edit_token(self):
        params = {'action': 'query',
                  'meta': 'tokens',
                  'type': 'csrf|rollback'}
        self._que_in.put({'action': 'get_edit_token',
                          'nosleep': True,
                          'type': 'params',
                          'params': params,
                          'update_progress': False})
        t = WikiPoster(self._que_in, self._que_out, self._api_url, self._cookies, self._user_agent)
        t.start()
        t.join()
        result = t.get_result()
        try:
            edit_token = result['query']['tokens']['csrftoken']
            rollback_token = result['query']['tokens']['rollbacktoken']
            if edit_token != '+\\':
                self._edit_token = edit_token
                self._rollback_token = rollback_token
                return True
        except Exception as e:
            self._log('获得编辑令牌时发生错误：%s' % e)
            # self._log('尝试换成登录数字站WIKI。')
            # return self._get_edit_token_nsite()
        return False

    # 检查是否获取了编辑令牌
    def has_edit_token(self):
        return True if self._edit_token else False

    # 设置间隔时间
    def set_sleep_time(self, number):
        self._sleep_time = int(number)

    # 设置超时时间
    def set_timeout(self, number):
        self._timeout = int(number)

    # 控制线程
    def _thread_do(self):
        return WikiPoster(self._que_in, self._que_out, self._api_url, self._cookies, self._user_agent, self._project,
                          self._permission_level, self._sleep_time, self._timeout)

    # 编辑页面
    def edit(self, title, text, filepath='', summary='', compare_flag=False):
        if compare_flag and os.path.exists(filepath):
            with open(filepath, 'r', encoding='UTF-8') as f:
                file_text = f.read()
                if file_text.strip() == text.strip():
                    return False
        if summary == '':
            summary = self._summary
        params = dict(action=(None, 'edit'),
                      token=(None, self._edit_token),
                      title=(None, str(title)),
                      text=(None, str(text)),
                      summary=(None, summary),
                      bot=(None, '1'))
        self._que_in.put({'action': 'edit',
                          'type': 'files',
                          'title': str(title),
                          'filepath': filepath,
                          'params': params})
        self._start_thread()

    def edit_tonly(self, title, text, data, filepath='', summary=''):
        if summary == '':
            summary = self._summary
        self._que_in.put({'action': 'edit_tonly',
                          'title': str(title),
                          'text': text,
                          'data': data,
                          'filepath': filepath,
                          'token': self._edit_token,
                          'summary': summary})
        self._start_thread()

    # 移动页面
    def move(self, title, new_title, summary='', movetalk=False, movesubpages=False, noredirect=False, delete=False):
        if summary == '':
            summary = self._summary
        params = {
            'action': (None, 'move'),
            'token': (None, self._edit_token),
            'from': (None, str(title)),
            'to': (None, str(new_title)),
            'reason': (None, summary),
            'ignorewarnings': (None, '1'),
        }
        if movetalk:
            params['movetalk'] = (None, '1')
        if movesubpages:
            params['movesubpages'] = (None, '1')
        if noredirect:
            params['noredirect'] = (None, '1')

        self._que_in.put({'action': 'move',
                          'type': 'files',
                          'title': str(title),
                          'delete_target': delete,
                          'params': params})
        self._start_thread()

    # 上传图片
    def upload_image(self, img_name, img_file, img_path, img_type='png', overwrite=False, keepfile=False, text=''):
        params = dict(action=(None, 'upload'),
                      token=(None, self._edit_token),
                      filename=(None, str(img_name)),
                      ignorewarnings=(None, '1'),
                      text=(None, text),
                      file=('images', img_file, 'image/'+img_type))
        self._que_in.put({'action': 'upload',
                          'overwrite': overwrite,
                          'keepfile': keepfile,
                          'img_path': img_path,
                          'type': 'files',
                          'title': str(img_name),
                          'params': params})
        self._start_thread()

    # 回退编辑
    def rollback(self, title, summary=''):
        if summary == '':
            summary = self._summary
        params = {
            'action': (None, 'rollback'),
            'title': (None, str(title)),
            'user': (None, 'DesertEagleF_bot'),
            'token': (None, self._rollback_token),
            'summary': (None, summary),
            'markbot': (None, '1'),
        }
        self._que_in.put({'action': 'rollback',
                          'type': 'files',
                          'title': str(title),
                          'params': params})
        self._start_thread()

    # 上传图片
    def upload_image_by_path(self, img_name, img_path, overwrite=False, keepfile=False, text=''):
        if not os.path.exists(img_path):
            print('图片不存在，无法上传：%s' % img_path)
            return
        # 修正文件名
        img_name = img_name.replace('/', '-')

        img_basename = os.path.basename(img_path)
        (_, img_type) = os.path.splitext(img_basename)
        if img_type[1:] in ['png', 'jpg', 'jpeg', 'gif']:
            img_type = img_type[1:]
        with open(img_path, 'rb') as f:
            img_file = f.read()

        params = dict(action=(None, 'upload'),
                      token=(None, self._edit_token),
                      filename=(None, str(img_name)),
                      ignorewarnings=(None, '1'),
                      text=(None, text),
                      file=('images', img_file, 'image/' + img_type))
        self._que_in.put({'action': 'upload',
                          'overwrite': overwrite,
                          'keepfile': keepfile,
                          'img_path': img_path,
                          'type': 'files',
                          'title': str(img_name),
                          'params': params})
        self._start_thread()

    # 检查目标页是否存在
    def exist(self, title):
        params = {'action': 'query',
                  'titles': str(title)}
        self._que_in.put({'action': 'exist',
                          'type': 'get',
                          'title': str(title),
                          'params': params})
        self._start_thread()

    # 检查Wiki是否存在
    def wiki_exist(self):
        params = {'action': 'query',
                  'titles': '首页'}
        self._que_in.put({'action': 'exist',
                          'type': 'get',
                          'update_progress': False,
                          'params': params})
        self._start_thread()

    # 删除页面（需要管理员权限）
    def delete(self, title, reason=''):
        if reason == '':
            reason = self._summary
        params = dict(action=(None, 'delete'),
                      token=(None, self._edit_token),
                      title=(None, str(title)),
                      reason=(None, reason))
        self._que_in.put({'action': 'delete',
                          'type': 'files',
                          'title': str(title),
                          'params': params})
        self._start_thread()

    # 恢复删除页面（需要行政员权限？）
    def undelete(self, title, reason=''):
        if reason == '':
            reason = self._summary

        params = dict(action=(None, 'undelete'),
                      token=(None, self._edit_token),
                      title=(None, str(title)),
                      reason=(None, reason))
        self._que_in.put({'action': 'undelete',
                          'type': 'files',
                          'title': str(title),
                          'params': params})
        self._start_thread()

    # 获得一个页面的rawtext
    def raw(self, title, filepath='', wikitextpath='', notice=True):
        self._que_in.put({'action': 'raw',
                          'filepath': filepath,
                          'wikitextpath': wikitextpath,
                          'notice': notice,
                          'title': str(title)})
        self._start_thread()

    # 按一个list批量获得页面内容
    def get_raw_text_by_list(self, title_list):
        for title in title_list:
            if not self.state_stop:
                self.raw(title)

    def get_result_rawtextlist(self):
        result = {}
        while not self._que_out.empty():
            r = self._que_out.get()
            result[r['title']] = r['rawtext']
        return result

    # 获得一个分类下全部页面列表
    def categorymembers(self, cate_name):
        self.clear_result()
        self._que_in.put({'action': 'categorymembers',
                          'title': str(cate_name),
                          'update_progress': False})
        self._start_thread()

    # 执行smw查询
    def smw_query(self, query):
        self.clear_result()
        params = {
            'action': 'ask'
        }
        self._que_in.put({'action': 'ask',
                          'query': query,
                          'params': params,
                          'update_progress': False})
        self._start_thread()

    # 按命名空间获得全条目列表
    def allpage(self, namespace_id):
        self.clear_result()
        self._que_in.put({'action': 'allpages',
                          'namespace_id': namespace_id,
                          'update_progress': False})
        self._start_thread()

    # 重新生成页面缓存
    def purge(self, titles):
        params = {
            'action': 'purge',
            'titles': titles,
            'forcelinkupdate': '1'
        }
        self._que_in.put({'action': 'purge',
                          'type': 'params',
                          'params': params})
        self._start_thread()

    # 用空编辑的方式重新生成页面缓存
    def purge_blank_edit(self, title, filepath='', wikitextpath=''):
        self._que_in.put({'action': 'purge_blank_edit',
                          'summary': self._summary,
                          'token': self._edit_token,
                          'filepath': filepath,
                          'wikitextpath': wikitextpath,
                          'title': title})
        self._start_thread()

    # 获取全部命名空间
    def allnamespace(self):
        self.clear_result()
        params = dict(action=(None, 'query'),
                      meta=(None, 'siteinfo'),
                      siprop=(None, 'namespaces'))
        self._que_in.put({'action': 'allnamespace',
                          'type': 'params',
                          'params': params,
                          })
        self._start_thread()
        self.wait_threads()
        return self.get_result()[0]

    # 获取指定命名空间中所有重定向
    def allredirects(self, namespace_id):
        self.clear_result()
        self._que_in.put({'action': 'allredirects',
                          'namespace_id': namespace_id})
        self._start_thread()

    # 获取指定命名空间中所有重定向
    def raw_by_id_list(self, page_id_list):
        self.clear_result()
        self._que_in.put({'action': 'raw_by_list',
                          'mode': 'id',
                          'page_id_list': page_id_list,
                          'update_progress': False})
        self._start_thread()

    # 获取图片的真实地址
    def get_image_info(self, titles):
        params = {
            'action': 'query',
            'titles': titles,
            'prop': 'imageinfo',
            'iiprop': 'url',
        }
        self._que_in.put({'action': 'image_info',
                          'type': 'params',
                          'params': params})
        self._start_thread()

    # 获取指定命名空间中所有重定向
    def raw_by_title_list(self, page_title_list):
        self.clear_result()
        self._que_in.put({'action': 'raw_by_list',
                          'mode': 'title',
                          'page_id_list': page_title_list,
                          'update_progress': False})
        self._start_thread()

    # 发起一次自定义请求
    def query(self, params):
        self._que_in.put({'action': 'query',
                          'type': 'params',
                          'params': params})
        self._start_thread()

    # 清除所有队列，来达到运行完当前事务后不再继续
    def stop(self):
        self.state_stop = True
        with self._que_in.mutex:
            self._que_in.queue.clear()
            for t in self._threads:
                t.stop()

    # 重新开始时进行的重置操作
    def reset(self):
        self.state_stop = False

    # 清空之前的result
    def clear_result(self):
        self.result = None

    # 有一部分字符可以做为PAGE_TITLE，但没法作为FILENAME
    @staticmethod
    def filename_fix(filename):
        char_list = ['\\', '/', ':', '*', '"']
        for i in range(0, len(char_list)):
            char = char_list[i]
            filename = filename.replace(char, '_%d_' % i)
        return filename

    @staticmethod
    def filename_fix_r(filename):
        char_list = ['\\', '/', ':', '*', '"']
        for i in range(len(char_list)-1, -1, -1):
            char = char_list[i]
            filename = filename.replace('_%d_' % i, char)
        return filename

    @staticmethod
    def template_name_fix(name):
        name = re.sub(r'<!--.*?-->', r'', name.strip())
        name = name[0].upper() + name[1:]
        name = name.replace('_', ' ')
        return name

    @staticmethod
    def get_img_dir(file_name):
        wiki_full_name = file_name.replace(' ', '_')
        wiki_full_name = wiki_full_name[0].upper() + wiki_full_name[1:]
        md5_hash = md5(wiki_full_name.encode()).hexdigest()
        return '%s/%s' % (md5_hash[0:1], md5_hash[0:2])


class WikiPoster(threading_danteng.ThreadDanteng):
    def __init__(self, que_in, que_out, api_url, cookies, agent, h_project=None, permission_level=1, sleep_time=2, timeout=30):
        super().__init__(que_in, que_out)
        self.api_url = api_url.lower()
        self.cookies = cookies
        self.agent = agent
        self.result = None
        self.h_project = h_project
        self._state_stop = False
        self._permission_level = permission_level
        self._sleep_time = int(sleep_time)
        self._timeout = int(timeout)

    def _exec(self, args):
        self.do(args)
        # 是否需要更新进度条
        progress = args['update_progress'] if 'update_progress' in args else True
        if self.h_project and progress:
            self.h_project.progress_plus()
        # 根据权限级别等待一些时间，防止502和503
        if 'nosleep' in args:
            if args['nosleep']:
                return
        # print(self._permission_level)
        if self._permission_level == 311:
            if self._sleep_time == 1:
                # print('等待0.5秒')
                time.sleep(0.5)
            else:
                # print('等待%d秒' % self._sleep_time)
                time.sleep(self._sleep_time)
        else:
            # print('等待%d秒' % self._sleep_time)
            time.sleep(self._sleep_time)

    def _log_output(self, log_str):
        if self.h_project:
            self.h_project.log(log_str)
        else:
            super()._log_output(log_str)

    def stop(self):
        self._state_stop = True

    def get_result(self):
        return self.result

    def do(self, args):
        try:
            if not self._state_stop:
                eval('self.%s(args)' % args['action'])
        except Exception as e:
            title = ''
            if 'title' in args:
                title = str(args['title'])
            elif 'params' in args and 'title' in args['params']:
                if type(args['params']['title']) == str:
                    title = str(args['params']['title'])
                elif type(args['params']['title']) == tuple:
                    title = str(args['params']['title'][1])
                else:
                    title = str(args['params']['title'])
            self._log('指令执行出错。指令类型：%s，标题：[%s]（%s）' % (args['action'], title, e))

    def check_usergroups(self, args):
        if not self._call(args):
            return False

    def login_bot(self, args):
        if self.do_login(args):
            self.result['cookies'] = self.cookies
            return True
        else:
            return False

    def do_login(self, args, token=None):
        if token:
            args['params']['lgtoken'] = (None, token)
        result = self._call(args)
        if result:
            if self.result['login']['result'] == 'Success':
                return True
            elif self.result['login']['result'] == 'NeedToken' and not token:
                return self.do_login(args, self.result['login']['token'])
            else:
                return False
        else:
            return False

    def login(self, args):
        # 获取登录令牌
        args['params'] = {
            'action': 'query',
            'meta': 'tokens',
            'type': 'login'
        }
        if not self._call(args):
            return False
        # 登录
        args['params'] = dict(action=(None, 'clientlogin'),
                              logintoken=(None, self.result['query']['tokens']['logintoken']),
                              username=(None, args['lgname']),
                              password=(None, args['lgpassword']),
                              loginreturnurl=(None, 'https://www.huijiwiki.com'),
                              rememberMe=(None, '1'))
        args['type'] = 'files'

        if self._call(args):
            self.result['cookies'] = self.cookies
            return True
        else:
            return False

    # 获取灰机用户信息
    def huijiuserinfo(self, args):
        return self._call(args)

    # 获得编辑令牌
    def get_edit_token(self, args):
        if not self._call(args):
            return False

    # 编辑
    def edit(self, args):
        if not self._call(args):
            return False

        if not self.result:
            self._error_log('请求时遇到错误，请检查。')
            return False
        if 'edit' in self.result:
            if self.result['edit']['result'] == 'Success':
                if 'nochange' in self.result['edit']:
                    self._log('[[%s]] 无改动。' % self.result['edit']['title'])
                    self.result['purge'] = 'nochange'
                else:
                    self._log('[[%s]] 更新完成。' % self.result['edit']['title'])
                    self.result['purge'] = 'done'

                self.save_file(args['filepath'], args['params']['text'][1])
                return True
            else:
                self._error_log('编辑时遇到错误，请检查。')
                return False

    # 将编辑内容保存到本地
    '''
    返回值：
    1   成功
    2   存在相同文件，跳过
    -1  文件名为空
    '''
    # 返回值
    # 1：成功
    #
    @staticmethod
    def save_file(file_path, file_text):
        if file_path == '':
            return -1
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, 'r', encoding='UTF-8') as f:
                if file_text == f.read():
                    return 2
        with open(file_path, 'w', encoding='UTF-8') as f:
            f.write(file_text)
        return 1

    # 编辑
    def edit_tonly(self, args):
        # 先获取页面
        self._notice = False
        raw_args = {'title': args['title']}
        self.raw(raw_args)

        # 替换模板内容
        if self.result == '':
            new_text = args['text']
        else:
            text_map = args['data']

            # 根据读取到的数据修改
            new_text = mwparserfromhell.parse(self.result)
            page_template_lists = new_text.filter_templates(recursive=False)
            page_template_max_index = {}

            # 替换
            for index in range(len(page_template_lists)):
                template_name = HuijiWiki.template_name_fix(page_template_lists[index].name)

                # 如果是需要处理的模板名称
                if template_name in text_map:
                    if template_name not in page_template_max_index:
                        page_template_max_index[template_name] = -1
                    page_template_max_index[template_name] += 1

                    replace_index = page_template_max_index[template_name]
                    if replace_index in text_map[template_name]:
                        new_text.replace(page_template_lists[index], text_map[template_name][replace_index])
            new_text = str(new_text)

            # 如果还有富余则添加
            for template_name in text_map:
                if template_name not in page_template_max_index:
                    page_template_max_index[template_name] = -1
                try:
                    max_index_number = max(text_map[template_name].keys())
                except ValueError:
                    max_index_number = -1
                for i in range(page_template_max_index[template_name]+1, max_index_number+1):
                    if i in text_map[template_name]:
                        new_text = new_text + '\n' + text_map[template_name][i]

            # 检查是否有变化
            if self.result == new_text:
                self._notice = True
                self._log('[[%s]] 无改动。' % args['title'])
                # 也要保存wikitext（因为本地wikitext对不上，保存一下才能防止下回对比失败）
                self.save_file(args['filepath'], args['text'])
                return False

        # 再重新编辑页面
        params = dict(action=(None, 'edit'),
                      token=(None, args['token']),
                      title=(None, args['title']),
                      text=(None, new_text),
                      summary=(None, args['summary']),
                      bot=(None, '1'))
        edit_args = {'action': 'edit',
                     'type': 'files',
                     'filepath': args['filepath'],
                     'params': params}
        self._notice = True
        if self.edit(edit_args):
            self.save_file(args['filepath'], args['text'])
            return True
        else:
            return False

    # 上传图片
    def upload(self, args):
        imgname = args['params']['filename'][1]
        # 如果不是强制覆盖模式，需要检查目标文件是否存在
        if not args['overwrite']:
            pagename = '文件:%s' % imgname
            self.exist({'action': 'exist',
                        'type': 'get',
                        'params': {'action': 'query', 'titles': pagename}})
            exist = self._que_out.get()
            if exist['exist']:
                self._log('“%s”已经存在，跳过上传。' % pagename)
                return False
        if not self._call(args):
            return False
        if not self.result:
            self._error_log('请求时遇到错误，请检查。')
            return False
        if 'error' in self.result:
            self._error_log('发生错误！img_name:%s , code: %s , info: %s' % (imgname, self.result['error']['code'], self.result['error']['info']))
            if self.result['error']['code'] == 'internal-error':
                self._log('正在尝试重新上传...')
                if self.upload(args):
                    return True
            return False
        elif 'upload' in self.result:
            if self.result['upload']['result'] == 'Success':
                self._log('“%s” 上传完毕。' % self.result['upload']['filename'])
                if not args['keepfile']:
                    os.remove(args['img_path'])
                return True
            else:
                self._error_log('上传时遇到错误，请检查。')
                return False

    # 页面是否存在
    def exist(self, args):
        result = {
            'exist': False,
            'error': False,
            'title': args['params']['titles']
        }
        if not self._call(args):
            result['error'] = True

        if self.result:
            try:
                if '-1' not in self.result['query']['pages']:
                    result['exist'] = True
            except Exception as e:
                result['error'] = True
                self._error_log('检查目标页是否存在时发生错误：%s' % e)
        else:
            result['error'] = True

        self._que_out.put(result)

    # 删除页面（需要管理员权限）
    def delete(self, args):
        if not self._call(args):
            return False
        title = args['params']['title'][1]

        if self.result:
            if 'delete' in self.result:
                self._log('[[%s]] 删除完成。' % self.result['delete']['title'])
                return True
            elif 'error' in self.result:
                if self.result['error']['code'] == 'missingtitle':
                    self._error_log('[[%s]] 页面不存在。' % title)
                elif self.result['error']['code'] == 'permissiondenied':
                    self._error_log('因为权限不足，无法删除页面 [[%s]] 。删除页面需要「管理员」权限，请检查。' % title)
                else:
                    self._error_log('发生错误！title:%s , code: %s , info: %s' % (title, self.result['error']['code'], self.result['error']['info']))
        else:
            self._error_log('遇到未知错误，请检查。')
        return False

    # 恢复删除页面（需要管理员）
    def undelete(self, args):
        if not self._call(args):
            return False

        title = args['params']['title'][1]

        if self.result:
            if 'undelete' in self.result:
                self._log('[[%s]] 恢复完成。（%s）' % (self.result['undelete']['title'], self.result['undelete']['reason']))
            elif 'error' in self.result:
                if self.result['error']['code'] == 'missingtitle':
                    self._log('[[%s]] 页面不存在。' % title)
                elif self.result['error']['code'] == 'cantundelete':
                    self._error_log('[[%s]] 无法恢复删除（可能页面并未被删除）。' % title)
                elif self.result['error']['code'] == 'permissiondenied':
                    self._error_log('因为权限不足，无法恢复页面 [[%s]] 。恢复被删除页面需要「管理员」权限，请检查。' % title)
                else:
                    self._error_log('发生错误！title:%s , code: %s , info: %s' % (
                        title, self.result['error']['code'], self.result['error']['info']))
        else:
            self._error_log('遇到未知错误，请检查。')
        return False

    def _call(self, args, retry_count=0):
        if self._state_stop:
            return

        response = None

        if args['type'] == 'params':
            args['params']['format'] = 'json'
            if self.cookies:
                response = self._post(self.api_url, params=args['params'], headers=self.agent, cookies=self.cookies)
            else:
                response = self._post(self.api_url, params=args['params'], headers=self.agent)
        elif args['type'] == 'files':
            args['params']['format'] = (None, 'json')
            if self.cookies:
                response = self._post(self.api_url, files=args['params'], headers=self.agent, cookies=self.cookies)
            else:
                response = self._post(self.api_url, files=args['params'], headers=self.agent)  # 应该怎么也不会用到
        elif args['type'] == 'get':
            args['params']['format'] = 'json'
            if self.cookies:
                response = self._get(self.api_url, params=args['params'], headers=self.agent, cookies=self.cookies)
            else:
                response = self._get(self.api_url, params=args['params'], headers=self.agent)

        # 超时5次
        if self._state_stop:
            return False
        if response.status_code in [502, 503, 504]:
            retry_count += 1
            retry_timer = min([int(retry_count/3)+1, 5])
            self._log('%d，请求出错：%s。%d秒后进行第%d次重试...' % (response.status_code, response.reason, retry_timer, retry_count))
            time.sleep(retry_timer)
            return self._call(args, retry_count)
        elif not response:
            return False
        elif response.status_code == 403:
            self._log('403，请求出错。请联系灰机进行检查')
        elif response.status_code == 200:
            if self.cookies:
                self.cookies.update(response.cookies)
            else:
                self.cookies = response.cookies
            self.result = json.loads(response.text, object_pairs_hook=OrderedDict)
            if 'error' in self.result:
                if 'ratelimited' in self.result['error']['code']:
                    if retry_count < 5:
                        self._log('超过限定的操作频率，10秒后重试...')
                        retry_count += 1
                        time.sleep(10)
                        return self._call(args, retry_count)
                elif 'internal_api_error_DBConnectionError' in self.result['error']['code']:
                    if retry_count < 5:
                        self._log('数据库连接错误，5秒后重试...')
                        retry_count += 1
                        time.sleep(5)
                        return self._call(args, retry_count)
                else:
                    return self._call_error(args, self.result['error'])
            else:
                return True
        else:
            title = ''
            if 'title' in args['params']:
                if type(args['params']['title']) == tuple:
                    title = args['params']['title'][1]
                else:
                    title = args['params']['title']

            if self._state_stop:
                return False

            if retry_count < 5:
                if title != '':
                    self._error_log('操作[[%s]]时连接错误（%d）。5秒后重试...' % (title, response.status_code))
                else:
                    self._error_log('连接错误（%d）。5秒后重试...' % response.status_code)
                retry_count += 1
                time.sleep(5)
                return self._call(args, retry_count)
            else:
                if title != '':
                    self._error_log('操作[[%s]]时连接错误（%d）。出错5次，该请求跳过。' % (title, response.status_code))
                else:
                    self._error_log('连接错误（%d）。出错5次，该请求跳过。' % response.status_code)
                return False

    def _call_error(self, args, error):
        result_status = False
        if 'onerror' in args:
            result_status = args['onerror'](args, error)

        if not result_status:
            self._error_code(error, args)
        return result_status

    def _post(self, url, headers, params='', files='', cookies=None):
        response = None
        for i in range(5):
            try:
                if params != '':
                    response = requests.post(url, params=params, headers=headers, cookies=cookies, timeout=self._timeout)
                elif files != '':
                    response = requests.post(url, files=files, headers=headers, cookies=cookies, timeout=self._timeout)
                break
            except:  # 超时重新下载
                if self._state_stop:
                    return False
                if i == 5:
                    self._log('连续操作超时%d次，操作失败！' % (i + 1))
                    return False
                else:
                    self._log('操作超时，正在重试（第%d次）...' % (i + 1))
        return response

    def _get(self, url, headers, params='', cookies=None):
        response = None
        for i in range(5):
            try:
                if params != '':
                    response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=self._timeout)
                break
            except:  # 超时重新下载
                if self._state_stop:
                    return False
                if i == 5:
                    self._log('连续操作超时%d次，操作失败！' % (i + 1))
                    return False
                else:
                    self._log('操作超时，正在重试（第%d次）...' % (i + 1))
        return response

    # 根据title获得raw_text
    def raw(self, args):
        url = self.api_url.replace('api.php', 'index.php?title=%s&action=raw&i=%d' % (quote(args['title']), random.randint(1, 1000000)))
        result = self._purely_get(url)
        if result.status_code == 200:
            result.encoding = 'utf-8'
            self.result = result.text
            if 'notice' in args:
                self._notice = args['notice']
            if 'filepath' in args and args['filepath'] != '':
                save_result = self.save_file(args['filepath'], result.text)
                if save_result == 1:
                    if 'wikitextpath' in args and args['wikitextpath'] != '':
                        self.save_file(args['wikitextpath'], result.text)
                    self._log('[[%s]] 源代码保存完成。' % args['title'])
                elif save_result == 2:
                    self._log('[[%s]] 源代码未修改。' % args['title'])
                else:
                    self._log('[[%s]] 源代码保存时，发生错误！错误代号：%d。' % (args['title'], save_result))
            else:
                self._log('[[%s]] 源代码读取完成。' % args['title'])
            if 'notice' in args:
                self._notice = not args['notice']
            self._que_out.put({'title': args['title'], 'rawtext': result.text})
            return True
        elif result.status_code == 404:
            self.result = ''
            self._log('[[%s]] 页面不存在。' % args['title'])
            return False
        else:
            self._log('[[%s]] 源代码读取出错：%s。' % (args['title'], result.status_code))
            return False

    def _purely_get(self, url):
        if self._state_stop:
            return False

        response = None
        for i in range(5):
            try:
                response = requests.get(url, headers=self.agent, cookies=self.cookies, timeout=self._timeout)
                break
            except:  # 超时重新下载
                if i == 5:
                    self._log('连续操作超时%d次，操作失败！' % (i + 1))
                    return False
                else:
                    self._log('操作超时，正在重试（第%d次）...' % (i + 1))
        return response

    def raw_by_list(self, args):
        limit = 500
        if args['mode'] == 'id':
            total = len(args['page_id_list'])
        else:
            total = len(args['page_title_list'])

        query_times = math.ceil(total / limit)
        if self.h_project:
            self.h_project.progress_plus_max(query_times)

        # 中间数据存储
        result = OrderedDict()
        for query_index in range(0, query_times):
            query_args = {
                'type': 'get',
                'params': {
                    'action': 'query',
                    'prop': 'revisions',
                    'rvprop': 'content',
                }
            }
            start = limit * query_index
            end = min(limit * (query_index + 1), total)
            if args['mode'] == 'id':
                query_args['params']['pageids'] = '|'.join([str(number) for number in args['page_id_list'][start:end]])
            else:
                query_args['params']['titles'] = '|'.join([str(number) for number in args['page_title_list'][start:end]])

            if self._state_stop:
                return False

            if not self._call(query_args):
                self._log('请求数据失败，将只返回已获取的数据。')
                return result

            result.update(self.result['query']['pages'])
            self._log('已经获取 %d 个条目的数据...' % len(result))
            if self.h_project:
                self.h_project.progress_plus()

        # 输出用
        output = OrderedDict()
        for page_id, page_info in result.items():
            page_info.update(page_info['revisions'][0])
            page_info['content'] = page_info['*']
            del page_info['revisions']
            del page_info['*']
            if args['mode'] == 'id':
                output[page_info['pageid']] = page_info
            else:
                output[page_info['title']] = page_info
        self._que_out.put(output)

    # 获取一个分类下所有文件列表
    def categorymembers(self, args):
        page_list = self._categorymembers(args['title'], '', [])
        self._que_out.put(page_list)

    # 实际执行收集数据工作的
    def _categorymembers(self, category_name, cmcontinue='', page_list=[]):
        args = {
            'type': 'get',
            'params': {
                'action': 'query',
                'list': 'categorymembers',
                'cmprop': 'title|ids|timestamp',
                'cmcontinue': cmcontinue,
                'cmtitle': '分类:%s' % category_name,
                'cmlimit': 500
            }
        }
        if not self._call(args):
            return []

        if self.result:
            if 'error' in self.result:
                self._error_code(self.result['error']['code'])
                self._log('获取【分类:%s】下的条目数据时出错：%s！' % (category_name, self.result['error']['info']))
                return []
            page_list.extend(self.result['query']['categorymembers'])
            if len(page_list) > 0:
                self._log('已经获取【分类:%s】下 %d 个条目数据...' % (category_name, len(page_list)))
            if 'continue' in self.result:
                cmcontinue = self.result['continue']['cmcontinue']
                return self._categorymembers(category_name, cmcontinue, page_list)
            else:
                if len(page_list) > 0:
                    self._log('【分类:%s】下的条目数据获取完成！' % category_name)
                else:
                    self._log('【分类:%s】下没有获取到任何条目数据！' % category_name)
                return page_list
        else:
            self._error_log('遇到未知错误，请检查。')
        return []

    # 执行smw查询
    def ask(self, args, result=None):
        if not result:
            result = {}

        args['type'] = 'get'
        # 生成查询语句
        query_text = args['query']
        try:
            query_text = '%s|limit=%d' % (query_text, int(args['limit']))
        except Exception as e:
            query_text = '%s|limit=5000' % query_text
        if 'offset' in args:
            query_text = '%s|offset=%d' % (query_text, args['offset'])
        else:
            # query_text = '%s|offset=0' % query_text
            args['offset'] = 0

        args['params']['query'] = query_text

        if self._call(args):
            if self.result:
                if len(self.result['query']['results']) == 0:
                    if 'query-continue-offset' in self.result:
                        self._log('获取数量已达API限制上限，如需调整请联系HuijiWiki管理员！')
                elif len(self.result['query']['results']) > 1:
                    count_old = len(result)
                    result.update(self.result['query']['results'])
                    if len(result) > count_old:
                        self._log('已经获取SMW查询条件下 %d 个条目数据...' % len(result))
                    if 'query-continue-offset' in self.result:
                        if self.result['query-continue-offset'] <= args['offset']:
                            self._log('offset超过设置的可用最大值，如需调整请联系HuijiWiki管理员！')
                        else:
                            args['offset'] = self.result['query-continue-offset']
                            return self.ask(args, result)
                if len(result) > 0:
                    self._log('SMW查询条件下的条目数据获取完成！')
                else:
                    self._log('SMW查询条件下，获取到任何条目数据！')
                self._que_out.put(result)
            else:
                self._error_log('遇到未知错误，请检查。')

    # 按namespace返回全页面列表
    def allpages(self, args):
        page_list = []
        page_list = self._allpages(args['namespace_id'], '', page_list)
        self._que_out.put(page_list)

    def _allpages(self, namespace_id, apcontinue='', page_list=[]):
        args = {
            'type': 'get',
            'params': {
                'action': 'query',
                'list': 'allpages',
                'apcontinue': apcontinue,
                'apnamespace': namespace_id,
                'aplimit': 500
            }
        }
        if not self._call(args):
            self._log('请求数据失败，将只返回已获取的数据。')
            return page_list

        if self.result:
            page_list.extend(self.result['query']['allpages'])
            if len(page_list) > 0:
                self._log('已经获取【命名空间:%s】下 %d 个条目数据...' % (namespace_id, len(page_list)))
            if 'continue' in self.result and not self._state_stop:
                apcontinue = self.result['continue']['apcontinue']
                return self._allpages(namespace_id, apcontinue, page_list)
            else:
                if len(page_list) > 0:
                    self._log('【命名空间:%s】下的条目数据获取完成！' % namespace_id)
                else:
                    self._log('【命名空间:%s】下没有获取到任何条目数据！' % namespace_id)
                return page_list
        else:
            self._error_log('遇到未知错误，请检查。')
        return []

    def purge(self, args):
        if not self._call(args):
            return False

        if not self.result:
            self._error_log('请求时遇到错误，请检查。')
            return False
        if 'purge' in self.result:
            try:
                total_count = len(self.result['purge'])
                if total_count == 0:
                    self._log('没有页面被刷新。')
                    return False
                first_page = self.result['purge'][0]['title']
                if total_count == 1:
                    self._log('[[%s]] 的刷新缓存申请提交完毕。' % first_page)
                else:
                    self._log('%d 个页面的刷新缓存申请提交完毕，请等待服务器处理。' % total_count)
                return True
            except Exception as e:
                self._error_log('遇到未知错误，请检查。错误信息：%s' % str(e))
                return False

    def purge_blank_edit(self, args):
        # 先获取页面
        self._notice = False
        raw_args = {'title': args['title']}
        # 如果有保存源代码工作，则一起完成
        if 'filepath' in args and args['filepath'] != '':
            raw_args['filepath'] = args['filepath']
        if 'wikitextpath' in args and args['wikitextpath'] != '':
            raw_args['wikitextpath'] = args['wikitextpath']
        if not self.raw(raw_args):
            self._notice = True
            self._log('[[%s]] 源代码获取失败，请联系软件作者排查原因。' % args['title'])
            return False
        # 再重新编辑页面
        params = dict(action=(None, 'edit'),
                      token=(None, args['token']),
                      title=(None, args['title']),
                      text=(None, self.result + '\n'),
                      summary=(None, args['summary']),
                      bot=(None, '1'))
        edit_args = {'action': 'edit',
                     'type': 'files',
                     'filepath': '',
                     'params': params}
        if self.edit(edit_args):
            self._notice = True
            if self.result['purge'] == 'nochange':
                if 'filepath' in args and args['filepath'] != '':
                    self._log('[[%s]] 源代码已保存，缓存刷新已完成。' % args['title'])
                else:
                    self._log('[[%s]] 缓存刷新已完成。' % args['title'])
            else:
                if 'filepath' in args and args['filepath'] != '':
                    self._log('[[%s]] 源代码已保存，缓存刷新过程中内容发生变化，请检查！' % args['title'])
                else:
                    self._log('[[%s]] 缓存刷新过程中内容发生变化，请检查！。' % args['title'])
            return True
        else:
            self._notice = True
            return False

    # 移动
    def move(self, args, silent=False):
        args['onerror'] = self.move_error

        if not self._call(args):
            return False

        if silent:
            return True

        if not self.result:
            self._error_log('请求时遇到错误，请检查。')
            return False
        if 'move' in self.result:
            self._log('已把[[%s]]移动到[[%s]]。' % (self.result['move']['from'], self.result['move']['to']))
            return True
        else:
            self._error_log('移动时遇到错误，请检查。')
            return False

    # 移动时出错检查
    def move_error(self, args, error):
        # 当目标页面已经存在，则删除目标页面重新移动
        if error['code'] == 'articleexists':
            if args['delete_target']:
                self._log('目标页面[[%s]]已经存在，准备删除…' % args['params']['to'][1])

                delete_args = {
                    'action': 'delete',
                    'type': 'files',
                    'title': str(args['params']['to'][1]),
                    'params': dict(
                        action=(None, 'delete'),
                        token=(None, args['params']['token'][1]),
                        title=(None, str(args['params']['to'][1])),
                        reason=(None, '移动页面时冲突，自动进行删除'))
                }
                if self.delete(delete_args):
                    # 重新移动，屏蔽掉通知
                    return self.move(args, True)
                else:
                    return False
        # 其他错误
        return False

    # 回退编辑
    def rollback(self, args):
        if not self._call(args):
            return False
        if not self.result:
            self._error_log('请求时遇到错误，请检查。')
            return False
        if 'rollback' in self.result:
            self._log('已回退' + self.result['rollback']['title'])
            return True
        else:
            self._error_log('请求时遇到错误，请检查。')
            return False

    # 获取全部namespace
    def allnamespace(self, args):
        if not self._call(args):
            return False

        # 整理结果
        ns_list = OrderedDict()
        for namespace_id, namespace_info in self.result['query']['namespaces'].items():
            namespace_id = int(namespace_id)
            # if namespace_id < 0:
            #     continue

            ns_list[namespace_id] = namespace_info['*']
        self._que_out.put(ns_list)
        return True

    # 获取全部namespace
    def allredirects(self, args):
        page_list = []
        page_list = self._allredirects(args['namespace_id'], '', page_list)
        self._que_out.put(page_list)

    def _allredirects(self, namespace_id, arcontinue='', page_list=[]):
        args = {
            'type': 'get',
            'params': {
                'action': 'query',
                'list': 'allredirects',
                'arnamespace': namespace_id,
                'arlimit': 500,
                'arprop': 'ids|title'
            }
        }
        if arcontinue != '':
            args['params']['arcontinue'] = arcontinue

        if self._state_stop:
            return page_list

        if not self._call(args):
            self._log('请求数据失败，将只返回已获取的数据。')
            return page_list

        if self.result:
            page_list.extend(self.result['query']['allredirects'])
            if len(page_list) > 0:
                self._log('已经获取【命名空间:%s】下 %d 个重定向数据...' % (namespace_id, len(page_list)))
            if 'continue' in self.result and not self._state_stop:
                arcontinue = self.result['continue']['arcontinue']
                return self._allredirects(namespace_id, arcontinue, page_list)
            else:
                if len(page_list) > 0:
                    self._log('【命名空间:%s】下的重定向数据获取完成！' % namespace_id)
                else:
                    self._log('【命名空间:%s】下没有获取到任何重定向数据！' % namespace_id)
                return page_list
        else:
            self._error_log('遇到未知错误，请检查。')
        return []

    # 请求图片真实地址
    def image_info(self, args):
        if not self._call(args):
            return False

        if not self.result:
            self._error_log('请求时遇到错误，请检查。')
            return False
        if 'query' in self.result:
            try:
                if len(self.result['query']['pages']) > 0:
                    self._que_out.put(self.result['query']['pages'])
                    self._log('成功获取 %d 个图片的数据。' % len(self.result['query']['pages']))
                    return True
                else:
                    self._log('没有请求到图片数据。')
                    return False
            except Exception as e:
                self._error_log('遇到未知错误，请检查。错误信息：%s' % str(e))
                return False

    # 执行一次自定义请求
    def query(self, args):
        if not self._call(args):
            return False
        else:
            self._que_out.put({'result': self.result})

    def _error_code(self, code, args=dict()):
        code_list = {
            'unknownerror': 'Unknown error: This usually means something crazy like a rare race condition occurred. If you get this error, retry your request until it succeeds or returns a more informative error message',
            'unknownerror-nocode': 'Unknown error',
            'unsupportednamespace': 'Pages in the Special namespace can\'t be edited',
            'protectednamespace-interface': 'You\'re not allowed to edit interface messages',
            'protectednamespace': 'You\'re not allowed to edit pages in the "namespace" namespace',
            'customcssjsprotected': 'You\'re not allowed to edit custom CSS and JavaScript pages',
            'cascadeprotected': 'The page you\'re trying to edit is protected because it\'s included in a cascade-protected page',
            'protectedpage': 'The "right" right is required to edit this page',
            'permissiondenied': '权限不足',
            'confirmemail': 'You must confirm your e-mail address before you can edit',
            'blocked': 'You have been blocked from editing',
            'autoblocked': 'Your IP address has been blocked automatically, because it was used by a blocked user',
            'ratelimited': '超过操作限制，请稍后再试。',
            'readonly': 'The wiki is currently in read-only mode',
            'badtoken': 'Invalid token (did you remember to urlencode it?)',
            'missingtitle': '请求的页面不存在',
            'mustbeposted': 'Type of your HTTP request message must be POST',
            'hookaborted': 'The modification you tried to make was aborted by an extension hook（Lua代码存在错误，请将代码放到编辑器中检查）',
            'nosuchpageid': 'There is no page with ID id',
            'nosuchrevid': 'There is no revision with ID id',
            'nosuchrcid': 'There is no change with rcid "id"',
            'nosuchuser': 'The user you specified doesn\'t exist',
            'invalidtitle': 'Bad title "title"',
            'invaliduser': 'Invalid username "username"',
            'assertbotfailed': '"assert=bot" has been used, but logged in user is not a bot',
            'assertuserfailed': '"assert=user" has been used, but user is not logged in',
            'readapidenied': 'You need read permission to use this module',
            'noapiwrite': 'Editing of this wiki through the API is disabled. Make sure the $wgEnableWriteAPI=true; statement is included in the wiki\'s LocalSettings.php file',
            'internal-error': '网络连接错误。',
            'cantundelete': '无法恢复删除（可能页面并未被删除）。'
        }
        if code['code'] in code_list:
            code_info = code_list[code['code']]
        else:
            code_info = code['info']

            code_info = code_info.replace('⧼', '').replace('⧽', '')

        if 'title' in args:
            if type(args['title']) == tuple:
                self._error_log('发生错误！执行页面标题：[[%s]]，错误代号：%s，错误信息：%s' % (args['title'][1], code['code'], code_info))
            else:
                self._error_log('发生错误！执行页面标题：[[%s]]，错误代号：%s，错误信息：%s' % (args['title'], code['code'], code_info))
        else:
            self._error_log('发生错误！错误代号：%s，错误信息：%s' % (code['code'], code_info))
