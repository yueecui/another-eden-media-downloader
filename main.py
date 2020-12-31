import argparse
from config_loader import config_loader
from data.download_data import download_data


def main():
    # 读取配置文件
    cfg = config_loader('config.ini')
    # 生成操作对象

    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='AnotherEden Chinese WIKI Updater (https://anothereden.huijiwiki.com)',
                                     epilog='Last Update: 2020-12-31')
    subparsers = parser.add_subparsers(title='sub modules')

    # 更新WIKI数据
    extract_parser = subparsers.add_parser('download', help='download game files')
    extract_parser.add_argument('type', nargs='?', type=str, default='all')
    extract_parser.set_defaults(callback=download_data)

    # 获取解析后的参数
    args = parser.parse_args()

    if hasattr(args, 'callback'):
        args.callback(cfg, args)
    else:
        print('error command')
        parser.print_help()


if __name__ == '__main__':
    main()
