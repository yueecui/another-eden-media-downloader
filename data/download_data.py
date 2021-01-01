import os
from data.another_eden_data import AnotherEdenData
from yuee_lib.danteng_lib import bool_value, read_file


def download_data(cfg, args):
    params = {
        'output_base_path': get_output_base_path(cfg),
        'manifest_info': read_manifest(cfg),
        'character_map': read_character_map(cfg),
        'save_character': bool_value(cfg['OPTION']['save_character']),
        'save_new_image': bool_value(cfg['OPTION']['save_new_image']),
        'save_new_wiki_image': bool_value(cfg['OPTION']['save_new_wiki_image']),
    }

    another_eden_data = AnotherEdenData(params)

    another_eden_data.download_files(args.type)


def read_manifest(cfg):
    file_text, result = read_file(cfg['DATA_PATH']['manifest_path'])
    assert result
    return file_text


def get_output_base_path(cfg):
    return cfg['DATA_PATH']['output_base_path']


def read_character_map(cfg):
    file_text, result = read_file(cfg['DATA_PATH']['character_map_path'])
    assert result
    character_map = {}
    for file_line in file_text.split('\n'):
        if file_line == '':
            continue
        char_info = file_line.split(',')
        char_id = char_info[0]
        char_name = char_info[1]
        char_id = '%05d' % int(char_id)
        character_map[char_id] = char_name
    return character_map
