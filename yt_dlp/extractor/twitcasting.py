# coding: utf-8
from __future__ import unicode_literals

import itertools
import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    clean_html,
    float_or_none,
    get_element_by_class,
    get_element_by_id,
    parse_duration,
    str_to_int,
    unified_timestamp,
    urlencode_postdata,
    try_get,
    urljoin,
)
from ..compat import compat_str


class TwitCastingBaseIE(InfoExtractor):
    pass


class TwitCastingIE(TwitCastingBaseIE):
    _VALID_URL = r'https?://(?:[^/]+\.)?twitcasting\.tv/(?P<uploader_id>[^/]+)/(?:movie|twplayer)/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://twitcasting.tv/ivetesangalo/movie/2357609',
        'md5': '745243cad58c4681dc752490f7540d7f',
        'info_dict': {
            'id': '2357609',
            'ext': 'mp4',
            'title': 'Live #2357609',
            'uploader_id': 'ivetesangalo',
            'description': 'Twitter Oficial da cantora brasileira Ivete Sangalo.',
            'thumbnail': r're:^https?://.*\.jpg$',
            'upload_date': '20110822',
            'timestamp': 1314010824,
            'duration': 32,
            'view_count': int,
        },
        'params': {
            'skip_download': True,
        },
    }, {
        'url': 'https://twitcasting.tv/mttbernardini/movie/3689740',
        'info_dict': {
            'id': '3689740',
            'ext': 'mp4',
            'title': 'Live playing something #3689740',
            'uploader_id': 'mttbernardini',
            'description': 'Salve, io sono Matto (ma con la e). Questa è la mia presentazione, in quanto sono letteralmente matto (nel senso di strano), con qualcosa in più.',
            'thumbnail': r're:^https?://.*\.jpg$',
            'upload_date': '20120212',
            'timestamp': 1329028024,
            'duration': 681,
            'view_count': int,
        },
        'params': {
            'skip_download': True,
            'videopassword': 'abc',
        },
    }]

    def _real_extract(self, url):
        uploader_id, video_id = re.match(self._VALID_URL, url).groups()

        video_password = self._downloader.params.get('videopassword')
        request_data = None
        if video_password:
            request_data = urlencode_postdata({
                'password': video_password,
            })
        webpage = self._download_webpage(
            url, video_id, data=request_data,
            headers={'Origin': 'https://twitcasting.tv'})

        title = try_get(
            webpage,
            (lambda x: self._html_search_meta(['og:title', 'twitter:title'], x, fatal=False)),
            compat_str)
        if not title:
            raise ExtractorError('Failed to extract title')

        video_js_data = try_get(
            webpage,
            lambda x: self._parse_json(self._search_regex(
                r"data-movie-playlist='([^']+?)'",
                x, 'movie playlist', default=None), video_id)["2"][0], dict) or {}
        is_live = 'data-status="online"' in webpage
        m3u8_url = try_get(
            webpage,
            (lambda x: self._search_regex(
                r'data-movie-url=(["\'])(?P<url>(?:(?!\1).)+)\1',
                x, 'm3u8 url', group='url', default=None),
             lambda x: video_js_data['source']['url'],
             lambda x: 'https://twitcasting.tv/%s/metastream.m3u8' % uploader_id
                if is_live else None),
            compat_str)

        if is_live:
            # use `m3u8` entry_protocol until EXT-X-MAP is properly supported by `m3u8_native` entry_protocol
            formats = self._extract_m3u8_formats(
                m3u8_url, video_id, 'mp4', m3u8_id='hls',
                headers={
                    'Accept': '*/*',
                    'Origin': 'https://twitcasting.tv',
                    'Referer': 'https://twitcasting.tv/',
                })
            self._sort_formats(formats)
        else:
            # This reduces the download of m3u8 playlist (2 -> 1)
            formats = [{
                'url': m3u8_url,
                'format_id': 'hls',
                'ext': 'mp4',
                'protocol': 'm3u8',
                'http_headers': {
                    'Accept': '*/*',
                    'Origin': 'https://twitcasting.tv',
                    'Referer': 'https://twitcasting.tv/',
                },
                'input_params': ['-re'],
            }]

        thumbnail = video_js_data.get('thumbnailUrl') or self._og_search_thumbnail(webpage)
        description = clean_html(get_element_by_id(
            'authorcomment', webpage)) or self._html_search_meta(
            ['description', 'og:description', 'twitter:description'], webpage)
        duration = float_or_none(video_js_data.get(
            'duration'), 1000) or parse_duration(clean_html(
                get_element_by_class('tw-player-duration-time', webpage)))
        view_count = str_to_int(self._search_regex(
            r'Total\s*:\s*([\d,]+)\s*Views', webpage, 'views', None))
        timestamp = unified_timestamp(self._search_regex(
            r'data-toggle="true"[^>]+datetime="([^"]+)"',
            webpage, 'datetime', None))

        return {
            'id': video_id,
            'title': title,
            'description': description,
            'thumbnail': thumbnail,
            'timestamp': timestamp,
            'uploader': uploader_id,
            'uploader_id': uploader_id,
            'duration': duration,
            'view_count': view_count,
            'formats': formats,
            'is_live': True,
        }


class TwitCastingLiveIE(InfoExtractor):
    _VALID_URL = r'https?://(?:[^/]+\.)?twitcasting\.tv/(?P<id>[^/]+)/?(?:[#?]|$)'
    _TESTS = [{
        'url': 'https://twitcasting.tv/ivetesangalo',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        uploader_id = self._match_id(url)
        self.to_screen(
            'Downloading live video of user {0}. '
            'Pass "https://twitcasting.tv/{0}/show" to download the history'.format(uploader_id))

        webpage = self._download_webpage(url, uploader_id)
        current_live = self._search_regex(
            (r'data-type="movie" data-id="(\d+)">',
             r'tw-sound-flag-open-link" data-id="(\d+)" style=',),
            webpage, 'current live ID', default=None)
        if not current_live:
            raise ExtractorError('The user is not currently live')
        return self.url_result('https://twitcasting.tv/%s/movie/%s' % (uploader_id, current_live))


class TwitCastingUserIE(InfoExtractor):
    _VALID_URL = r'https?://(?:[^/]+\.)?twitcasting\.tv/(?P<id>[^/]+)/show/?(?:[#?]|$)'
    _TESTS = [{
        'url': 'https://twitcasting.tv/noriyukicas/show',
        'only_matching': True,
    }]

    def _entries(self, uploader_id):
        base_url = next_url = 'https://twitcasting.tv/%s/show' % uploader_id
        for page_num in itertools.count(1):
            webpage = self._download_webpage(
                next_url, uploader_id, query={'filter': 'watchable'}, note='Downloading page %d' % page_num)
            matches = re.finditer(
                r'''(?isx)<a\s+class="tw-movie-thumbnail"\s*href="(?P<url>/[^/]+/movie/\d+)"\s*>.+?</a>''',
                webpage)
            for mobj in matches:
                yield self.url_result(urljoin(base_url, mobj.group('url')))

            next_url = self._search_regex(
                r'<a href="(/%s/show/%d-\d+)[?"]' % (re.escape(uploader_id), page_num),
                webpage, 'next url', default=None)
            next_url = urljoin(base_url, next_url)
            if not next_url:
                return

    def _real_extract(self, url):
        uploader_id = self._match_id(url)
        return self.playlist_result(
            self._entries(uploader_id), uploader_id, '%s - Live History' % uploader_id)
