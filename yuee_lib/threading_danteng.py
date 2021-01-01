from time import strftime, localtime
import threading
import queue


class ObjectDanteng(object):
    # 复制此段作为初始化函数
    # def __init__(self):
    #     super().__init__()
    #     self._log_title = 'DANTENG'

    def __init__(self):
        self._name = None
        self._log_toggle = True
        self._threads = []
        self._max_threads_number = 10
        self._log_title = 'DANTENG'
        self._que_in = queue.Queue()
        self._que_out = queue.Queue()

    def _log(self, log_str):
        if self._log_toggle:
            if self._name != '':
                log_str = "[%s:%s] " % (self._log_title, self._name) + log_str
            else:
                log_str = "[%s] " % self._log_title + log_str
        self._log_output(log_str)

    def _log_output(self, log_str):
        timestr = strftime("[%H:%M:%S]", localtime())
        log_str = timestr + log_str
        try:
            log_str = log_str.encode('gbk').decode('gbk')
        except Exception as e:
            if type(e) == UnicodeEncodeError:
                log_str = '** 本LOG中有无法显示的字符 **'
        print(log_str)

    # 开始执行事务
    # 复制此函数修改
    # def do_something(self, args):
    #     self._que_in.put(args)
    #     self._start_thread()

    # 开始线程
    def _start_thread(self):
        if len(self._threads) >= self._max_threads_number:
            new_threads = []
            for t_index in range(0, len(self._threads)):
                t = self._threads[t_index]
                if t.isAlive():
                    new_threads.append(t)
                    t.setName('线程-%02d' % (len(new_threads) + 1))
            self._threads = new_threads
        if len(self._threads) < self._max_threads_number:
            t = self._thread_do()
            t.setName('线程-%02d' % (len(self._threads) + 1))
            t.start()
            self._threads.append(t)

    # 调用不同的类来解决问题
    # 复制此函数修改
    def _thread_do(self):
        pass
        # return ClassName(self._que_in, self._que_out)

    # 等待所有线程完成工作
    def wait_threads(self):
        for t in self._threads:
            t.join()
        self._threads.clear()

    # 通用获得结果用函数
    def get_result(self):
        result = []
        while not self._que_out.empty():
            r = self._que_out.get()
            result.append(r)
        return result

    # 设置最大线程数
    def set_thread_number(self, number):
        self._max_threads_number = int(number)


class ThreadDanteng(threading.Thread):
    # 复制此段作为初始化函数
    # def __init__(self, que_in, que_out):
    #     super().__init__(que_in, que_out)

    def __init__(self, que_in, que_out):
        super().__init__()
        self._que_in = que_in
        self._que_out = que_out
        self._notice = True
        self._result = None

    def _log(self, log_str):
        if self._notice:
            if self._name != '':
                log_str = "[%s] " % self._name + log_str
            else:
                log_str = "[线程] " + log_str
            self._log_output(log_str)

    def _error_log(self, log_str):
        if self._name != '':
            log_str = "[%s][错误] " % self._name + log_str
        else:
            log_str = "[线程][错误] " + log_str
        self._log_output(log_str)

    def _log_output(self, log_str):
        timestr = strftime("[%H:%M:%S]", localtime())
        log_str = timestr + log_str
        try:
            log_str = log_str.encode('gbk').decode('gbk')
        except Exception as e:
            if type(e) == UnicodeEncodeError:
                log_str = '** 本LOG中有无法显示的字符 **'
        print(log_str)

    def run(self):
        while True:
            if not self._que_in.empty():
                self._exec(self._que_in.get())
                self._que_in.task_done()
            else:
                break

    # 执行入口
    def _exec(self, args):
        self._do(args)
        # ...  通用处理

    # 具体操作
    def _do(self, args):
        try:
            eval('self.%s(args)' % args['action'])
        except AttributeError as e:
            self._log('调用的方法不存在')
