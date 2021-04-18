# coding: utf-8
from __future__ import unicode_literals

from datetime import datetime
import itertools
import json
import base64
import random

from .common import InfoExtractor
from ..utils import (
    ExtractorError, std_headers,
    update_url_query,
    random_uuidv4,
    try_get,
)
from ..compat import (
    compat_urlparse,
    compat_urllib_parse_urlencode,
    compat_str,
)


class MildomBaseIE(InfoExtractor):
    _GUEST_ID = None
    _DISPATCHER_CONFIG = None

    _MILDOM_PROXY_HOSTS = (
        'bookish-octo-barnacle.vercel.app',
        'free-mountain-goal.glitch.me',)

    def _call_api(self, url, video_id, query={}, note='Downloading JSON metadata', init=False):
        url = update_url_query(url, self._common_queries(query, init=init))
        return self._download_json(url, video_id, note=note)['body']

    def _common_queries(self, query={}, init=False):
        dc = self._fetch_dispatcher_config()
        r = {
            'timestamp': self.iso_timestamp(),
            '__guest_id': '' if init else self.guest_id(),
            '__location': dc['location'],
            '__country': dc['country'],
            '__cluster': dc['cluster'],
            '__platform': 'web',
            '__la': self.lang_code(),
            '__pcv': 'v2.9.44',
            'sfr': 'pc',
            'accessToken': '',
        }
        r.update(query)
        return r

    def _fetch_dispatcher_config(self):
        if not self._DISPATCHER_CONFIG:
            try:
                tmp = self._download_json(
                    'https://disp.mildom.com/serverListV2', 'initialization',
                    note='Downloading dispatcher_config', data=json.dumps({
                        'protover': 0,
                        'data': base64.b64encode(json.dumps({
                            'fr': 'web',
                            'sfr': 'pc',
                            'devi': 'Windows',
                            'la': 'ja',
                            'gid': None,
                            'loc': '',
                            'clu': '',
                            'wh': '1919*810',  # don't google this magic number!
                            'rtm': self.iso_timestamp(),
                            'ua': std_headers['User-Agent'],
                        }).encode('utf8')).decode('utf8').replace('\n', ''),
                    }).encode('utf8'))
                self._DISPATCHER_CONFIG = self._parse_json(base64.b64decode(tmp['data']), 'initialization')
            except ExtractorError:
                self._DISPATCHER_CONFIG = self._download_json(
                    'https://%s/api/mildom/dispatcher_config' % self._mildom_proxy_host(), 'initialization',
                    note='Downloading dispatcher_config fallback')
        return self._DISPATCHER_CONFIG

    @staticmethod
    def iso_timestamp():
        'new Date().toISOString()'
        return datetime.utcnow().isoformat()[0:-3] + 'Z'

    def guest_id(self):
        'getGuestId'
        if self._GUEST_ID:
            return self._GUEST_ID
        self._GUEST_ID = try_get(
            self, (
                lambda x: x._call_api(
                    'https://cloudac.mildom.com/nonolive/gappserv/guest/h5init', 'initialization',
                    note='Downloading guest token', init=True)['guest_id'] or None,
                lambda x: x._get_cookies('https://www.mildom.com').get('gid').value,
                lambda x: x._get_cookies('https://m.mildom.com').get('gid').value,
            ), compat_str) or ''
        return self._GUEST_ID

    def lang_code(self):
        'getCurrentLangCode'
        return 'ja'

    def _mildom_proxy_host(self):
        return random.choice(self._MILDOM_PROXY_HOSTS)

# python3 -m youtube_dl https://www.mildom.com/10534224 -o - 2>&1 | ffmpeg -i - -f null /dev/null


class MildomIE(MildomBaseIE):
    IE_NAME = 'mildom'
    IE_DESC = 'Record ongoing live by specific user in Mildom'
    _VALID_URL = r'https?://(?:(?:www|m)\.)?mildom\.com/(?P<id>\d+)'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        url = 'https://www.mildom.com/%s' % video_id

        webpage = self._download_webpage(url, video_id)

        enterstudio = self._call_api(
            'https://cloudac.mildom.com/nonolive/gappserv/live/enterstudio', video_id,
            note='Downloading live metadata', query={'user_id': video_id})
        result_video_id = enterstudio.get('log_id', video_id)

        # e.g. Minecraft
        title = try_get(
            enterstudio, (
                lambda x: self._html_search_meta('twitter:description', webpage),
                lambda x: x['anchor_intro'],
            ), compat_str)
        # e.g. me playing Minecraft
        description = try_get(
            enterstudio, (
                lambda x: x['intro'],
                lambda x: x['live_intro'],
            ), compat_str)
        # e.g. Donald F. Trump
        uploader = try_get(
            enterstudio, (
                lambda x: self._html_search_meta('twitter:title', webpage),
                lambda x: x['loginname'],
            ), compat_str)

        servers = self._call_api(
            'https://cloudac.mildom.com/nonolive/gappserv/live/liveserver', result_video_id,
            note='Downloading live server list', query={
                'user_id': video_id,
                'live_server_type': 'hls',
            })

        stream_query = self._common_queries({
            'streamReqId': random_uuidv4(),
            'is_lhls': '0',
        })
        m3u8_url = update_url_query(servers['stream_server'] + '/%s_master.m3u8' % video_id, stream_query)
        formats = self._extract_m3u8_formats(m3u8_url, result_video_id, 'mp4', headers={
            'Referer': 'https://www.mildom.com/',
            'Origin': 'https://www.mildom.com',
        }, note='Downloading m3u8 information')
        del stream_query['streamReqId'], stream_query['timestamp']
        for fmt in formats:
            # source code behind bookish-octo-barnacle.vercel.app is here: https://github.com/nao20010128nao/bookish-octo-barnacle/
            parsed = compat_urlparse.urlparse(fmt['url'])
            parsed = parsed._replace(
                netloc=self._mildom_proxy_host(),
                query=compat_urllib_parse_urlencode(stream_query, True),
                path='/api/mildom' + parsed.path)
            fmt['url'] = compat_urlparse.urlunparse(parsed)

        self._sort_formats(formats)

        return {
            'id': result_video_id,
            'title': title,
            'description': description,
            'uploader': uploader,
            'uploader_id': video_id,
            'formats': formats,
            'is_live': True,
        }


class MildomVodIE(MildomBaseIE):
    IE_NAME = 'mildom:vod'
    IE_DESC = 'Download a VOD in Mildom'
    _VALID_URL = r'https?://(?:(?:www|m)\.)?mildom\.com/playback/(?P<user_id>\d+)/(?P<id>(?P=user_id)-[a-zA-Z0-9]+)'

    def _real_extract(self, url):
        m = self._valid_url_re().match(url)
        user_id, video_id = m.group('user_id'), m.group('id')
        url = 'https://www.mildom.com/playback/%s/%s' % (user_id, video_id)

        webpage = self._download_webpage(url, video_id)

        autoplay = self._call_api(
            'https://cloudac.mildom.com/nonolive/videocontent/playback/getPlaybackDetail', video_id,
            note='Downloading playback metadata', query={
                'v_id': video_id,
            })['playback']

        # e.g. Minecraft
        title = try_get(
            autoplay, (
                lambda x: self._html_search_meta('og:description', webpage),
                lambda x: x['title'],
            ), compat_str)
        # e.g. me playing Minecraft
        description = try_get(
            autoplay, (
                lambda x: x['video_intro'],
            ), compat_str)
        # e.g. Donald F. Trump
        uploader = try_get(
            autoplay, (
                lambda x: x['author_info']['login_name'],
            ), compat_str)

        audio_formats = [{
            'url': autoplay['audio_url'],
            'format_id': 'audio',
            'protocol': 'm3u8_native',
            'vcodec': 'none',
            'acodec': 'aac',
        }]
        video_formats = []
        for fmt in autoplay['video_link']:
            video_formats.append({
                'format_id': 'video-%s' % fmt['name'],
                'url': fmt['url'],
                'protocol': 'm3u8_native',
                'width': fmt['level'] * autoplay['video_width'] // autoplay['video_height'],
                'height': fmt['level'],
                'vcodec': 'h264',
                'acodec': 'aac',
            })

        stream_query = self._common_queries({
            'is_lhls': '0',
        })
        del stream_query['timestamp']
        formats = audio_formats + video_formats
        for fmt in formats:
            fmt['ext'] = 'mp4'
            parsed = compat_urlparse.urlparse(fmt['url'])
            stream_query['path'] = parsed.path[5:]
            parsed = parsed._replace(
                netloc=self._mildom_proxy_host(),
                query=compat_urllib_parse_urlencode(stream_query, True),
                path='/api/mildom/vod2/proxy')
            fmt['url'] = compat_urlparse.urlunparse(parsed)

        self._sort_formats(formats)

        return {
            'id': video_id,
            'title': title,
            'description': description,
            'uploader': uploader,
            'uploader_id': user_id,
            'formats': formats,
        }


# User's ongoing live can be done via MildomIE, so this is only for VODs
class MildomUserVodIE(MildomBaseIE):
    IE_NAME = 'mildom:user:vod'
    IE_DESC = 'Download all VODs from specific user in Mildom'
    _VALID_URL = r'https?://(?:(?:www|m)\.)?mildom\.com/profile/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://www.mildom.com/profile/10093333',
        'info_dict': {
            'id': '10093333',
            'title': 'Uploads from ねこばたけ',
        },
        'playlist_mincount': 351,
    }]

    def _real_extract(self, url):
        user_id = self._match_id(url)

        self._downloader.report_warning('To download ongoing live, please use "https://www.mildom.com/%s" instead. This will list up VODs belonging to user.' % user_id)

        profile = self._call_api(
            'https://cloudac.mildom.com/nonolive/gappserv/user/profileV2', user_id,
            query={'user_id': user_id}, note='Downloading user profile')['user_info']

        results = []
        for page in itertools.count(1):
            reply = self._call_api(
                'https://cloudac.mildom.com/nonolive/videocontent/profile/playbackList',
                user_id, note='Downloading page %d' % page, query={
                    'user_id': user_id,
                    'page': page,
                    'limit': '30',
                })
            if not reply:
                break
            results.extend('https://www.mildom.com/playback/%s/%s' % (user_id, x['v_id']) for x in reply)
        return self.playlist_result([
            self.url_result(u, ie=MildomVodIE.ie_key()) for u in results
        ], user_id, 'Uploads from %s' % profile['loginname'])
