import json
import os
import re
import requests
from yuee_lib.danteng_lib import log, load_json, save_json, get, check_folder
from yuee_lib.danteng_downloader import Downloader


class AnotherEdenData:
    FILE_PATH = 'files'
    NEW_PATH = 'new'
    WIKI_PATH = 'wiki'
    CHARACTER_PATH = 'character'
    VERSION_PATH = 'version'

    def __init__(self, params):
        self._cdn_url = ''
        self._version = ''
        self._data = None
        self._save_character = params['save_character']
        self._save_new_image = params['save_new_image']
        self._save_new_wiki_image = params['save_new_wiki_image']

        self._miss_log = []  # 角色ID和角色name缺失的情况

        self._character_map = params['character_map']
        self._output_base_path = params['output_base_path']
        self._check_version(params['manifest_info'])

    # 检查版本信息
    def _check_version(self, manifest_info):
        if manifest_info is None:
            return
        if type(manifest_info) == str:
            manifest_info = json.loads(manifest_info)

        version_url = manifest_info['remoteManifestUrl']
        response = get(version_url)
        if response is None:
            raise Exception(f'请求最初版本数据时失败！请检查')

        version_info = json.loads(response.text)
        self._cdn_url = version_info['packageUrl']
        self._version = version_info['version']
        self._data = version_info  # 临时数据
        self._load_data()

    # 加载全版本信息
    def _load_data(self):
        data_file_path = os.path.join(self._output_base_path, self.VERSION_PATH, f'{self._version}.json')
        data = load_json(data_file_path)
        if data is None:
            log(f'版本[{self._version}]的信息不存在，正在重新下载…')
            self._download_version_info()
            save_json(self._data, data_file_path)
        else:
            log(f'已从本地加载版本[{self._version}]的信息')
            self._data = data

    def _download_version_info(self):
        # 初始化数据包
        data = {
            'assets': {},
            'url': [],
            'version': self._version,
            'packageUrl': self._cdn_url,
        }
        log(f'正在下载版本[{self._version}]信息的第1部分……')
        self._download_data(data, manifest_url=self._data['remoteManifestUrl'])

        index = 1
        while True:
            index += 1
            key = f'manifests/phase.manifest.{index}'
            if key not in data['assets']:
                break
            log(f'正在下载版本[{self._version}]信息的第{index}部分……')
            self._download_data(data, version_url=f'{self._cdn_url}/{data["assets"][key]["path"]}')

        self._data = data
        log(f'版本[{self._version}]的信息下载完成！')

    @staticmethod
    def _download_data(data, manifest_url='', version_url=''):
        assert manifest_url != '' or version_url != ''
        if manifest_url == '' and version_url != '':
            response = get(version_url)
            if response is None:
                raise Exception(f'请求Version数据时失败，URL {version_url}，请检查')
            version_info = json.loads(response.text)
            manifest_url = version_info['remoteManifestUrl']

        assert manifest_url != ''

        response = get(manifest_url)
        if response is None:
            raise Exception(f'请求Manifest版本数据时失败，URL {manifest_url}，请检查')

        temp = json.loads(response.text)
        data['assets'].update(temp['assets'])
        data['url'].append({
            'remoteManifestUrl': temp['remoteManifestUrl'],
            'remoteVersionUrl': temp['remoteVersionUrl'],
        })

    # 可用type
    # all：全部文件下载
    # image：只包括png，以及骨骼动画用到的.atlas和.skel
    # audio：只包括ogg音频
    # media：包括image和audio
    def download_files(self, filter_type='all'):
        log(f'开始下载版本[{self._version}]的数据，过滤类型为[{filter_type}]')

        downloader = Downloader()

        for file_path, file_info in self._data['assets'].items():
            if len(file_path) < 6 or file_path[:6] != 'files/':
                continue
            (folder_name, file_name) = os.path.split(file_path)
            folder_name = folder_name[6:]
            (file_basename, file_type) = os.path.splitext(file_name)

            if filter_type == 'image' and file_type not in ['.png', '.atlas', '.skel']:
                continue
            if filter_type == 'audio' and file_type not in ['.ogg']:
                continue
            if filter_type == 'media' and file_type not in ['.png', '.atlas', '.skel', '.ogg']:
                continue

            original_path = os.path.join(self._output_base_path, self.FILE_PATH, folder_name, file_name)
            if os.path.exists(original_path) and os.path.getsize(original_path) == file_info['size']:
                continue

            save_list = [original_path]

            if self._save_character and file_type in ['.png', '.atlas', '.skel', '.ogg']:
                file_path = self._get_character_save_path(folder_name, file_name)
                if file_path:
                    save_list.append(file_path)
            if self._save_new_image and file_type == '.png':
                file_path = self._get_new_image_path(folder_name, file_name)
                if file_path:
                    save_list.append(file_path)
            if self._save_new_wiki_image and file_type == '.png':
                file_path = self._get_new_wiki_image_path(folder_name, file_name)
                if file_path:
                    save_list.append(file_path)

            url = f'{self._cdn_url}/{file_info["path"]}'

            downloader.download_multi_copies(url, save_list)
        downloader.wait_threads()

    def _get_character_save_path(self, folder_name, file_name):
        (file_basename, file_type) = os.path.splitext(file_name)
        if folder_name.find('character/') == 0:
            if folder_name.find('dummy') > -1:
                return None
            find = re.findall(r'character/(.+?)/(\d{3})(\d{5})(\d)', folder_name)
            assert find
            if find[0][1] != '101':
                return None
            image_type = find[0][0]
            character_id = find[0][2]
            character_name = self._get_character_name(character_id)
            return os.path.join(self._output_base_path, self.CHARACTER_PATH, f'{character_id}_{character_name}', f'{image_type}_{file_name}')
        elif folder_name == 'sound/voice':
            find = re.findall(r'voice_(\w+?)_(.*)', file_basename)
            assert find
            character_name = find[0][0]
            if character_name == 'skit':  # 小剧场
                find = re.findall(r'(\d+)_(.+)', find[0][1])
                assert find
                index = find[0][0]
                voice_name = find[0][1]
                return os.path.join(self._output_base_path, self.CHARACTER_PATH, 'skit', index, f'{voice_name}{file_type}')
            else:
                character_id = self._get_character_id(character_name)
                voice_name = find[0][1]
                return os.path.join(self._output_base_path, self.CHARACTER_PATH, f'{character_id}_{character_name}', 'voice', f'{voice_name}{file_type}')
        elif folder_name == 'spine/characterSpine':
            find = re.findall(r'104(\d{5})\d', file_basename)
            if not find:
                return None
            character_id = find[0]
            character_name = self._get_character_name(character_id)
            return os.path.join(self._output_base_path, self.CHARACTER_PATH, f'{character_id}_{character_name}', 'spine', file_name)
        return None

    def _get_new_image_path(self, folder_name, file_name):
        return os.path.join(self._output_base_path, self.NEW_PATH, f'{folder_name.replace("/", "__")}__{file_name}')

    def _get_new_wiki_image_path(self, folder_name, file_name):
        (file_basename, file_type) = os.path.splitext(file_name)
        if folder_name.find('character/') == 0:
            if folder_name.find('dummy') > -1:
                return None
            find = re.findall(r'character/(.+?)/(\d{3})(\d{5})(\d)', folder_name)
            assert find
            if find[0][1] != '101':
                return None
            image_type = find[0][0]
            character_id = find[0][2]
            sub_id = find[0][3]

            find = re.findall(r'101'+character_id+sub_id+'(_s\d)?(_rank5)?', file_basename)
            assert find
            style = find[0][0]
            rarity = find[0][1]
            if rarity == '':
                fixname = ''
            elif rarity == '_rank5' and style == '':
                fixname = '_r5'
            elif style != '':
                fixname = style
            else:
                raise Exception(f'预期外的角色图片名称[{folder_name}/{file_name}]，请检查')

            if image_type == 'base':
                pass  # 不添加额外字符串
            elif image_type == 'command':
                fixname += '_icon'
            elif image_type == 'party_portrait':
                fixname += '_party'
            elif image_type == 'talk_ui_portrait':
                fixname += '_talk'

            return os.path.join(self._output_base_path, self.WIKI_PATH, f'{character_id}{fixname}{file_type}')

        return None

    def _get_character_name(self, character_id):
        character_id = '%05d' % int(character_id)
        character_name = self._character_map.get(character_id)
        if character_name is None:
            if character_id not in self._miss_log:
                self._miss_log.append(character_id)
                if int(character_id) < 40000:
                    log(f'角色ID [{character_id}] 没有对应的名字，请注意添加！')
                    character_name = 'unknown'
        return character_name

    def _get_character_id(self, character_name):
        for char_id, char_name in self._character_map.items():
            if char_name == character_name:
                return char_id
        if character_name not in self._miss_log:
            self._miss_log.append(character_name)
            log(f'角色名称 [{character_name}] 没有对应的ID，请注意添加！')
        return '99999'

