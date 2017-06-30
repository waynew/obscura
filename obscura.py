#!/usr/bin/env python4

import argparse
import configparser
import logging
import os
import pathlib
import platform
import sys
import time

from datetime import datetime


logger = logging.getLogger('obscura')
logger.addHandler(logging.FileHandler(pathlib.Path.home().joinpath('.obscura.log')))
Path = pathlib.Path
#if args.debug:
#    logger.setLevel(logging.DEBUG)
#else:
#    logger.setLevel(logging.INFO)


class ProgressBar:
    def __init__(self, count, length=20, character='*', empty_char='.'):
        self.current = 0
        self.count = count
        self.length = length
        self.character = character
        self.empty_char = empty_char

    def __enter__(self):
        return self

    def __exit__(self, *args):
        print()

    def update(self, count):
        self.current += count
        scale = int(self.length * self.current / self.count)
        print('[{c:{0.empty_char}<{0.length}.{0.length}}] {0.current}/{0.count}'.format(self, c=self.character*scale), end='\r')
        sys.stdout.flush()


def get_date_reader(select=None):
    try:
        import exifread
        def exif_reader(f):
            import pprint
            exifdata = exifread.process_file(f, stop_tag='DateTimeOriginal', details=False)
            logger.debug(f'EXIF data for {f.name} - {pprint.pformat(exifdata)}')
            date = exifdata['EXIF DateTimeOriginal']
            date = datetime.strptime(date.values, '%Y:%m:%d %H:%M:%S')
            return date
        return exif_reader
    except ImportError:
        print("WARNING: exif-py is not installed, only using the file timestamps which could be wrong.", file=sys.stderr)
        def stat_fallback(f):
            path = Path(f.name)
            # https://stackoverflow.com/a/39501288/344286
            if platform.system() == 'Windows':
                date = datetime.fromtimestamp(path.stat().st_ctime)
            else:
                try:
                    date = datetime.fromtimestamp(path.stat().st_birthtime)
                except AttributeError:
                    date = datetime.fromtimestamp(path.stat().st_mtime)
            return date
        return stat_fallback


def load_config():
    conf = configparser.ConfigParser(interpolation=None)
    conf_file = pathlib.Path.home().joinpath('.obscura.conf')
    if not conf.read([conf_file]):
        print(f'WARNING: No Obscura config file found at {conf_file}', file=sys.stderr)
    return {
        'src': Path(conf['obscura']['src_folder']),
        'dst': Path(conf['obscura']['dst_folder']),
        'extensions': [ext.strip() for ext in conf['obscura']['file_formats'].split(',')],
        'path_fmt': conf['obscura']['path_format'],
        'stat_fallback': conf.getboolean('obscura', 'file_timestamp_fallback'),
        'log_file': Path(conf['obscura']['logpath']),
        'log_level': conf['obscura']['loglevel'].upper(),
        'copy_files': conf.getboolean('obscura', 'copy_files'),
    }


def copy_all(*, src_folder, dst_folder, date_reader=None, config=None):
    logger.debug('Copying files from %r to %r', src_folder, dst_folder)
    date_reader = date_reader or get_date_reader()
    config = config or load_config()
    paths_to_walk = [src_folder]
    to_copy = set()
    cr2 = None
    jpg = None


    start = time.time()
    while paths_to_walk:
        next_path = paths_to_walk.pop()
        logger.debug('Walking %r', next_path)
        try:
            for thing in next_path.iterdir():
                if thing.is_dir():
                    logger.debug('Adding %r to folders to walk', thing)
                    paths_to_walk.append(thing)
                elif thing.suffix.lower() in config['extensions']:
                    logger.debug('Adding %r to files to copy', thing)
                    to_copy.add(thing)
        except PermissionError as e:
            print('Warning:', e)

    logger.info(f'{len(to_copy)} filenames collected')
    with ProgressBar(len(to_copy)) as bar:
        for src_file in to_copy:
            with open(src_file, 'rb') as src:
                try:
                    date = date_reader(src)
                except KeyError:
                    if not config['stat_fallback']:
                        logger.exception('Unable to get EXIF data for file', str(src_file))
                        raise

                    logger.exception('Unable to get EXIF datetime for %r falling back to stat time', str(src_file))

                    # https://stackoverflow.com/a/39501288/344286
                    if platform.system() == 'Windows':
                        date = datetime.fromtimestamp(src_file.stat().st_ctime)
                    else:
                        try:
                            date = datetime.fromtimestamp(src_file.stat().st_birthtime)
                        except AttributeError:
                            date = datetime.fromtimestamp(src_file.stat().st_mtime)
                dst_file = dst_folder.joinpath(
                    f'{date:{config["path_fmt"]}}{src_file.suffix.lower()}',
                )
                logger.info(f'Copying {str(src_file)!r} to {str(dst_file)!r}')
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # To copy
                src.seek(0)
                dst_file.write_bytes(src.read())

                # To move
                #src_file.replace(dst_file)

            bar.update(1)
    end = time.time()

    lapsed = end-start
    seconds = lapsed % 60
    left = (lapsed - seconds)/60
    minutes = int(left % 60)
    left = (left - minutes)/60
    hours = int(left % 24)

    time_spent = ''
    if hours:
        time_spent += f'{hours}h'
    time_spent += f'{minutes}m'
    time_spent += f'{seconds:.2f}s'

    print('Elapsed:', time_spent)


def init():
    conf_file = pathlib.Path.home().joinpath('.obscura.conf')
    no_choices = ('', 'n', 'no', 'nyet', 'nein', 'no, sir', 'no way')
    if conf_file.exists():
        overwrite = input('WARNING: Config file already exists, would you like to overwrite with defaults? (y/[n]): ')
        if overwrite.lower() in no_choices:
            print('Nothing to do here.')
            return

    default_fmt = f'%Y{os.path.sep}%m{os.path.sep}%d{os.path.sep}%Y%m%d_%H%M%S'
    curdir = pathlib.Path().resolve()
    default_dst = pathlib.Path(input(f'Default photo destination (full path - default {curdir}): ')).resolve()
    default_src = pathlib.Path(input('Default source drive/folder (empty to prompt every time): ').strip())
    default_fmt = input(f'Default path format [empty for {default_fmt!r}]: ').strip() or default_fmt
    file_timestamp_fallback = input('Fallback to using file timestamp if EXIF parse fails? (y/[n]): ').lower() in no_choices
    default_logpath = pathlib.Path.home().joinpath('.obscura.log').resolve()
    logpath = pathlib.Path(input(f'Log path (default {default_logpath}): ').strip() or default_logpath).resolve()
    loglevel = input('Log Level (debug/info/[warning]/error): ').strip() or 'warning'
    copy_files = (input('Copy or move files? ([copy]/move): ').lower().strip() or 'copy') == 'copy'
    file_formats = [ext.strip() for ext in
        (input('File extensions (default: .jpg, .jpeg, .cr2, .png, .mov, .tiff, .nef): ').strip()
        or '.jpg, .jpeg, .cr2, .png, .mov').split(',')
    ]

    config = configparser.ConfigParser(interpolation=None)
    config['obscura'] = {
        'dst_folder': default_dst,
        'src_folder': default_src,
        'file_formats': ','.join(file_formats),
        'path_format': default_fmt,
        'file_timestamp_fallback': file_timestamp_fallback,
        'logpath': logpath,
        'loglevel': loglevel,
        'copy_files': copy_files,
    }
    with open(conf_file, 'w') as f:
        config.write(f)


if __name__ == '__main__':
    config = load_config()
    logger.addHandler(logging.FileHandler(config['log_file'], mode=config.get('log_file_mode', 'w')))
    logger.setLevel(getattr(logging, config['log_level']))
    logger.info('Logging configured, obscura starting up...')

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--init', action='store_true')
    parser.add_argument('source', default=config['src'],
        nargs='?',
        help=f'path to pictures to import - default {config["src"]}')
    args = parser.parse_args()
    logger.debug('Args: %r', args)

    if args.init:
        init()
    elif config.get('copy_files'):
        logger.debug('Copying files')
        copy_all(src_folder=args.source, dst_folder=config['dst'])
    else:
        sys.exit('Move mode not yet supported')

    sys.exit(0)

