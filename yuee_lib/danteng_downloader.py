import requests
import os
import threading_danteng
from danteng_lib import check_folder


class Downloader(threading_danteng.ObjectDanteng):
    # 复制此段作为初始化函数
    def __init__(self, title='DOWNLOADER'):
        super().__init__()
        requests.packages.urllib3.disable_warnings()
        self._log_title = title
        self._threads = []
        self._max_threads_number = 10
        self._try_count = 50
        self._block_size = 1024 * 1024 * 5  # 默认5M一个块

    def set_try_count(self, number):
        self._try_count = number

    def set_block_size(self, size):
        self._block_size = size

    # 尝试下载
    def download(self, url, path, filename, headers={}, log_handle=None):
        return self.download_multi_copies(url, [os.path.join(path, filename)], headers=headers, log_handle=log_handle)

    # 多保存目标下载
    def download_multi_copies(self, url, save_list, headers={}, log_handle=None):
        if len(save_list) == 0:
            return False
        filename = os.path.split(save_list[0])[1]
        args = {
            'url': url,
            'filename': filename,
            'save_list': save_list,
            'block_size': self._block_size,
            'segment': False,
            'headers': headers,
            'log_handle': log_handle,
        }
        self._que_in.put(args)
        self._start_thread()
        return True

    # 分块下载
    def segment_download(self, url, filename, s_index, s_total):
        args = {
            'url': url,
            'filename': filename,
            's_index': s_index,
            's_total': s_total,
            'block_size': self._block_size,
            'segment': True,
        }
        self._que_in.put(args)
        self._start_thread()
        return True

    # 调用不同的类来解决问题
    # 复制此函数修改
    def _thread_do(self):
        return DownloaderThread(self._que_in, self._que_out, self._try_count)


# 同时下载文件的线程
class DownloaderThread(threading_danteng.ThreadDanteng):
    def __init__(self, que_in, que_out, try_count):
        self._try_count = try_count
        super().__init__(que_in, que_out)

    # 覆盖此函数
    def _exec(self, args):
        if not args['segment']:
            self._head(args)
        else:
            self._segment_download(args)

    def _head(self, args):
        if 'headers' in args:
            headers = args['headers']
        else:
            headers = {}
        count = 0
        while True:
            count += 1
            try:
                response = requests.get(args['url'], headers=headers, timeout=30, verify=False)
                if response.status_code == 200:
                    break
                elif response.status_code == 404:
                    if not args['log_handle'] is None:
                        args['log_handle'].write(args['url'] + '\n')
                    self._log('<%s>文件不存在（404），已跳过！' % args['filename'])
                    return False
                else:
                    print('%s 下载出错，请检查' % response.status_code)
            except Exception as e:  # 超时重新下载
                if count < self._try_count:
                    self._log('<%s>下载时，连接超时%d次，正在重试！' % (args['filename'], count))
                else:
                    self._log('<%s>下载时，连接超时%d次，已跳过！' % (args['filename'], count))
                    return False

        try:
            file_size = int(response.headers.get('Content-Length'))
        except TypeError:
            file_size = 0
        if file_size < args['block_size'] or args['block_size'] < 0:
            download_response = self._download(args)
            if not download_response['stat']:
                self._log('<%s>下载失败！（%s）' % (args['filename'], download_response['msg']))
                return False
            for save_path in args['save_list']:
                check_folder(save_path, 1)
                with open(save_path, 'wb') as file:
                    file.write(download_response['content'])

            self._log('文件<%s>下载成功！' % args['filename'])
            return True
        else:
            block_num = (file_size + args['block_size'] - 1) // args['block_size']
            self._log('文件<%s>大小：%s，分为%d块进行下载' % (args['filename'], get_size_desc(file_size), block_num))
            segment_downloader = Downloader(title=args['filename'])
            segment_downloader.set_thread_number(10)
            for i in range(block_num):
                segment_downloader.segment_download(args['url'], args['filename'], i, block_num)
            segment_downloader.wait_threads()
            segment_data = segment_downloader.get_result()
            segment_data.sort(key=lambda s: s['s_index'])
            self._log('开始保存文件<%s>...' % args['filename'])

            for save_path in args['save_list']:
                check_folder(save_path, 1)
                with open(save_path, 'wb') as file:
                    file.write(b''.join([s['content'] for s in segment_data]))

            self._log('文件<%s>下载成功！' % args['filename'])

    def _download(self, args):
        if 'headers' in args:
            headers = args['headers']
        else:
            headers = {}
        count = 0
        while True:
            count += 1
            try:
                response = requests.get(args['url'], headers=headers, timeout=30, verify=False)
                if response.status_code in [200, 206]:
                    break
                elif response.status_code in [404]:
                    return {'stat': False, 'msg': '404 目标不存在'}
                else:
                    print('%s 下载出错，请检查' % response.status_code)
            except Exception as e:  # 超时重新下载
                if count < self._try_count:
                    self._log('<%s>下载时，连接超时%d次，正在重试！' % (args['filename'], count))
                else:
                    self._log('<%s>下载时，连接超时%d次，已跳过！' % (args['filename'], count))
                    return {'stat': False, 'content': ''}
        return {'stat': True, 'content': response.content}

    def _segment_download(self, args):
        start, end = get_start_and_end(args)
        args['headers'] = {'Range': 'Bytes=%s-%s' % (start, end), 'Accept-Encoding': '*', 'Accept-Ranges': 'bytes'}
        download_response = self._download(args)
        if not download_response['stat']:
            self._log('<%s>第%d/%d块下载失败！（%s）' % (args['filename'], args['s_index'] + 1, args['s_total'], download_response['msg']))
            return False
        self._que_out.put({
            's_index': args['s_index'],
            'content': download_response['content'],
        })
        self._log('<%s>第%d/%d(%.2f%%)块下载完成！' % (
        args['filename'], args['s_index'] + 1, args['s_total'], self._que_out.qsize() / args['s_total']*100))


_SIZE_UNIT = {
    1: '',
    2: 'KB',
    3: 'MB',
    4: 'GB',
}


def get_size_desc(size):
    for i in range(1, 5):
        if size < 1024 ^ i:
            if size == int(size):
                return '%d%s' % (size, _SIZE_UNIT[i])
            else:
                return '%.2f%s' % (size, _SIZE_UNIT[i])
        else:
            size /= 1024


def get_start_and_end(args):
    if args['s_index'] == args['s_total'] - 1:
        return args['s_index'] * args['block_size'], ''
    else:
        return args['s_index'] * args['block_size'], (args['s_index']+1) * args['block_size'] - 1
