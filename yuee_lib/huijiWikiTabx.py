# 处理和维护HuijiWiki中Tabx类数据的模块
import json
from collections import OrderedDict
from danteng_lib import log, read_file
from danteng_excel import read_sheet_from_xlsx
from SaveToExcel import save_to_excel
import os


# wiki：用于操作的huijiWiki对象
# title：存储Tabx的数据所在页面名称
# main_key：默认为''，如果不为空字符串的话，将使用header中的这个项目当作key来生成数据
# load：如果是只生成空的用于编辑，不需要加载线上版本，就置为False
class HuijiWikiTabx(object):
    def __init__(self, wiki, title, main_key='', load=True):
        self._wiki = wiki
        self._title = title
        self._no_key = main_key == ''
        self._key = main_key
        self._original_data = OrderedDict()
        self._header = []  # 数据的表头
        self._key_list = []
        self._raw_text = ''
        self._data = OrderedDict()  # 数据内容
        # 初始化表格（下载数据、生成表头、生成数据表）
        # 如果有load设为false，则不读取线上数据。用于本地直接上传文件
        if load:
            self._ready = self.load() and self.generate_header() and self.generate_data()

    # 生成迭代器对象
    def __iter__(self):
        for row_index, row_content in self._data.items():
            yield row_index, row_content

    # 创建一个新的表
    def create_new_tabx(self):
        self._original_data = OrderedDict([
            ('license', 'CC0-1.0'),
            ('description', OrderedDict([
                ('en', 'table description'),
            ])),
            ('sources', 'Create by huijiWikiTabx'),
            ('schema', OrderedDict([
                ('fields', [])
            ])),
            ('data', [])
        ])
        self.generate_header(True)
        self.generate_data(True)
        self._ready = True
        return True

    # 读取线上数据到本地
    def load(self):
        self._wiki.raw(self._title, notice=False)
        self._wiki.wait_threads()
        result = self._wiki.get_result()
        if len(result) == 1:
            self._raw_text = result[0]['rawtext']
            self._original_data = json.loads(self._raw_text, object_pairs_hook=OrderedDict)
            return True
        else:
            return False

    # 判断是否准备就绪
    def ready(self):
        return self._ready

    # 生成表头
    def generate_header(self, is_new=False):
        # 获取header
        self._header = []
        if is_new:
            return True
        if 'schema' not in self._original_data:
            log('[[%s]]数据有误：未找到表头字段，请检查。' % self._title)
            return False
        if 'fields' not in self._original_data['schema']:
            log('[[%s]]数据有误：未找到表头字段，请检查。' % self._title)
            return False
        for field in self._original_data['schema']['fields']:
            self._header.append(field['title']['en'])
        if self._key != '' and self._key not in self._header:
            log('[[%s]]数据有误：表头字段中未找到当作KEY的“%s”，请检查。' % (self._title, self._key))
            return False
        return True

    # 获取表头
    def get_header(self):
        return self._header

    # 获取表头
    def get_raw_text(self):
        return self._raw_text

    # 获取原始表头
    def get_original_header(self):
        return self._original_data['schema']['fields']

    # 设置原始表头
    def set_original_header(self, header):
        self._original_data['schema']['fields'] = header
        self.generate_header()

    # 生成数据
    def generate_data(self, is_new=False):
        self._data = OrderedDict()
        if is_new:
            return True
        if 'data' not in self._original_data:
            log('[[%s]]数据有误：未找到内容数据，请检查。' % self._title)
            return False
        for index in range(0, len(self._original_data['data'])):
            row_data = OrderedDict()
            for key_index in range(0, len(self._header)):
                if self._header[key_index][-2:] == '[]':
                    header = self._header[key_index][:-2]
                    if self._original_data['data'][index][key_index] is None or self._original_data['data'][index][key_index] == '':
                        row_data[header] = []
                    else:
                        row_data[header] = str(self._original_data['data'][index][key_index]).split(';')
                else:
                    row_data[self._header[key_index]] = self._original_data['data'][index][key_index]

            key = index if self._key == '' else row_data[self._key]
            if self._key != '' and key is None:
                # log('[[%s]]数据有误：第 %d 行当作KEY的“%s”值是None，请检查。' % (self._title, index+1, self._key))
                continue
            self._data[key] = row_data
        return True

    # 获取全部数据
    def get_all_data(self):
        return self._data

    # 获取数据长度
    def length(self):
        return len(self._data)

    # 查询数据中是否有某个key
    def has_key(self, key):
        return key in self._data

    # 查询数据中是否有某个key
    def has_row(self, key):
        return key in self._data

    # 获取指定key的row_data
    def get_row(self, key):
        if key in self._data:
            return self._data[key].copy()
        else:
            return None

    # 添加/修改新的行
    def mod_row(self, key, data):
        temp_data = OrderedDict()
        # for key_index in range(0, len(self._header)):
        #     header_name = self._header[key_index]
        for key_name in self._header:
            if key_name[-2:] == '[]':
                key_name = key_name[:-2]

            # 判断ID部分不用find_key_name
            if key_name == self._key:
                temp_data[key_name] = key
            elif key_name in data:
                if type(data[key_name]) == str:
                    temp_data[key_name] = data[key_name].strip()
                else:
                    temp_data[key_name] = data[key_name]
            else:
                temp_data[key_name] = None
        self._data[key] = temp_data

    # 添加新的行
    # 保存回服务器
    def save(self, wikitext_path=None):
        if len(self._header) == 0:
            return False
        header_type_map = {}

        new_data = []
        for row_data in self._data.values():
            temp_row = []
            for key_name in self._header:
                if key_name[-2:] == '[]':
                    key_name = key_name[:-2]
                    if key_name in row_data and type(row_data[key_name]) == list and len(row_data[key_name]) > 0:
                        temp_row.append(';'.join([str(v) for v in row_data[key_name]]))
                    else:
                        temp_row.append(None)
                else:
                    if key_name in row_data and row_data[key_name] != '':
                        temp_row.append(row_data[key_name])
                    else:
                        temp_row.append(None)
            new_data.append(temp_row)
        self._original_data['data'] = new_data

        page_content = json.dumps(self._original_data, ensure_ascii=False, separators=(',', ':'))
        if wikitext_path:
            wikitext_filepath = os.path.join(wikitext_path, self._wiki.filename_fix('%s.txt' % self._title))
            # wikitext_content, wikitext_result = read_file(wikitext_filepath)
            # if wikitext_result and wikitext_content.strip() == page_content.strip():
            #     return

            self._wiki.edit(self._title, page_content, filepath=wikitext_filepath, compare_flag=True)
        else:
            self._wiki.edit(self._title, page_content)
        self._wiki.wait_threads()
        self._raw_text = page_content
        if wikitext_path:
            self.save_raw_to_wikitext(wikitext_path)
        return True

    # 打开一个excel
    def open_xlsx(self, xlsx_path):
        xlsx_data = read_sheet_from_xlsx(xlsx_path, sheet_index=0)
        xlsx_data = xlsx_data[list(xlsx_data.keys())[0]]

        new_data = OrderedDict([
            ('license', 'CC0-1.0'),
            ('description', OrderedDict([
                ('en', '请输入简要描述')
            ])),
            ('sources', '导入自 %s by Bot' % os.path.split(xlsx_path)[1]),
            ('schema', OrderedDict([
                ('fields', []),
            ])),
            ('data', [])
        ])

        # 首先把A1放进header
        top_data_key = list(xlsx_data['data'].keys())[0]
        # ex_data_key = list(xlsx_data['data'][top_data_key][0].keys())[0]
        ex_data = xlsx_data['data'][top_data_key][0]

        # header_info
        headers_type_map = OrderedDict()

        # A1格数据
        header_name = self.get_header_name(xlsx_data['a1'].lower())
        header_type = self.get_value_type(top_data_key)
        new_data['schema']['fields'].append(OrderedDict([
            ('name', header_name),
            ('type', header_type),
            ('title', OrderedDict([
                ('en', xlsx_data['a1'])
            ]))
        ]))
        headers_type_map[header_name] = header_type

        # 把其他表头放进去
        for header in xlsx_data['header']:
            header_name = self.get_header_name(header.lower())
            header_type = self.get_value_type(ex_data[header])
            new_data['schema']['fields'].append(OrderedDict([
                ('name', header_name),
                ('type', header_type),
                ('title', OrderedDict([
                    ('en', header)
                ]))
            ]))
            headers_type_map[header_name] = header_type

        for data_key, info_set in xlsx_data['data'].items():
            for info in info_set:
                temp_data = [data_key]
                for header in xlsx_data['header']:
                    header_name = self.get_header_name(header.lower())
                    if headers_type_map[header_name] == 'string':
                        info[header] = str(info[header]).strip()
                    temp_data.append(info[header])
                new_data['data'].append(temp_data)

        self._original_data = new_data
        return self.generate_header() and self.generate_data()

    @staticmethod
    def get_value_type(value):
        value_type = type(value)
        value_type_text = 'string'
        if value_type in [int, float]:
            value_type_text = 'number'
        elif value_type == bool:
            value_type_text = 'boolean'
        return value_type_text

    @staticmethod
    def get_header_name(header):
        output = header
        if len(header) >= 2 and output[-2:] == '[]':
            output = output[:-2]
        return output

    # 保存为xlsx
    def save_as_xlsx(self, xlsx_path, save_sheet_name):
        # 生成excel数据
        headers = {save_sheet_name: self.get_header()}
        contents = {save_sheet_name: {}}

        # headers = OrderedDict([
        #     (save_sheet_name, [])
        # ])
        # contents = OrderedDict([
        #     (save_sheet_name, OrderedDict())
        # ])

        for item_key, info in self._data.items():
            row_data = OrderedDict()
            for header in self.get_header():
                dict_key = self.get_header_name(header)
                if dict_key in info:
                    if type(info[dict_key]) == list:
                        row_data[header] = ';'.join(info[dict_key])
                    else:
                        row_data[header] = info[dict_key]
                else:
                    row_data[header] = None
            contents[save_sheet_name][item_key] = row_data

        save_to_excel(headers, contents, xlsx_path)
        return True

    # 与WIKITEXT进行对比
    def compare_with_wikitext(self, wikitext_path):
        page_title = self._wiki.filename_fix(self._title)
        wikitext_filepath = os.path.join(wikitext_path, '%s.txt' % page_title)

        file_content, result = read_file(wikitext_filepath)
        if result:
            return file_content.strip() == self.get_raw_text().strip()
        else:
            return False

    # 保存源代码为wikitext
    def save_raw_to_wikitext(self, wikitext_path):
        page_title = self._wiki.filename_fix(self._title)
        wikitext_filepath = os.path.join(wikitext_path, '%s.txt' % page_title)

        with open(wikitext_filepath, 'w', encoding='UTF-8') as f:
            f.write(self.get_raw_text())

    # 从一个list导入数据
    # list中每个项目是一个dict
    # 每个header的类型由第一次出现时的属性决定
    def import_from_list(self, data_list, sources=''):
        new_data = OrderedDict([
            ('license', 'CC0-1.0'),
            ('description', OrderedDict([
                ('en', '请输入简要描述')
            ])),
            ('sources', sources),
            ('schema', OrderedDict([
                ('fields', []),
            ])),
            ('data', [])
        ])

        # 记录已经有哪些header了
        already_header = []

        # 整理数据（list转成字符串），并且梳理出header
        for data_content in data_list:
            for header in list(data_content.keys()):
                header_name = header
                value = data_content[header]
                if type(value) == list:
                    header_name = '%s[]' % header
                    value = ';'.join(value)
                    data_content[header_name] = value
                if header_name not in already_header:
                    new_data['schema']['fields'].append(OrderedDict([
                        ('name', header_name),
                        ('type', self.get_value_type(value)),
                        ('title', OrderedDict([
                            ('en', header)
                        ]))
                    ]))

                    already_header.append(header_name)

        for data_content in data_list:
            temp_data = []
            for header in already_header:
                temp_data.append(data_content[header])
            new_data['data'].append(temp_data)

        self._original_data = new_data
        return self.generate_header() and self.generate_data()
