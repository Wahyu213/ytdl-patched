# coding: utf-8
from __future__ import unicode_literals

import re

from .common import InfoExtractor
from ..utils import clean_html, parse_duration, unescapeHTML, urljoin


class NhkBaseIE(InfoExtractor):
    _API_URL_TEMPLATE = 'https://api.nhk.or.jp/nhkworld/%sod%slist/v7a/%s/%s/%s/all%s.json'
    _BASE_URL_REGEX = r'https?://www3\.nhk\.or\.jp/nhkworld/(?P<lang>[a-z]{2})/ondemand'
    _TYPE_REGEX = r'/(?P<type>video|audio)/'

    def _call_api(self, m_id, lang, is_video, is_episode, is_clip):
        return self._download_json(
            self._API_URL_TEMPLATE % (
                'v' if is_video else 'r',
                'clip' if is_clip else 'esd',
                'episode' if is_episode else 'program',
                m_id, lang, '/all' if is_video else ''),
            m_id, query={'apikey': 'EJfK8jdS57GqlupFgAfAAwr573q01y6k'})['data']['episodes'] or []

    def _extract_episode_info(self, url, episode=None):
        fetch_episode = episode is None
        lang, m_type, episode_id = NhkVodIE._match_valid_url(url).groups()
        if episode_id.isdigit():
            episode_id = episode_id[:4] + '-' + episode_id[4:]

        is_video = m_type == 'video'
        if fetch_episode:
            episode = self._call_api(
                episode_id, lang, is_video, True, episode_id[:4] == '9999')[0]
        title = episode.get('sub_title_clean') or episode['sub_title']

        def get_clean_field(key):
            return episode.get(key + '_clean') or episode.get(key)

        series = get_clean_field('title')

        thumbnails = []
        for s, w, h in [('', 640, 360), ('_l', 1280, 720)]:
            img_path = episode.get('image' + s)
            if not img_path:
                continue
            thumbnails.append({
                'id': '%dp' % h,
                'height': h,
                'width': w,
                'url': 'https://www3.nhk.or.jp' + img_path,
            })

        info = {
            'id': episode_id + '-' + lang,
            'title': '%s - %s' % (series, title) if series and title else title,
            'description': get_clean_field('description'),
            'thumbnails': thumbnails,
            'series': series,
            'episode': title,
        }
        if is_video:
            vod_id = episode['vod_id']
            info.update({
                '_type': 'url_transparent',
                'ie_key': 'Piksel',
                'url': 'https://player.piksel.com/v/refid/nhkworld/prefid/' + vod_id,
                'id': vod_id,
            })
        else:
            if fetch_episode:
                audio_path = episode['audio']['audio']
                info['formats'] = self._extract_m3u8_formats(
                    'https://nhkworld-vh.akamaihd.net/i%s/master.m3u8' % audio_path,
                    episode_id, 'm4a', entry_protocol='m3u8_native',
                    m3u8_id='hls', fatal=False)
                for f in info['formats']:
                    f['language'] = lang
                self._sort_formats(info['formats'])
            else:
                info.update({
                    '_type': 'url_transparent',
                    'ie_key': NhkVodIE.ie_key(),
                    'url': url,
                })
        return info


class NhkVodIE(NhkBaseIE):
    _VALID_URL = r'%s%s(?P<id>\d{7}|[^/]+?-\d{8}-[0-9a-z]+)' % (NhkBaseIE._BASE_URL_REGEX, NhkBaseIE._TYPE_REGEX)
    # Content available only for a limited period of time. Visit
    # https://www3.nhk.or.jp/nhkworld/en/ondemand/ for working samples.
    _TESTS = [{
        # video clip
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/video/9999011/',
        'md5': '7a90abcfe610ec22a6bfe15bd46b30ca',
        'info_dict': {
            'id': 'a95j5iza',
            'ext': 'mp4',
            'title': "Dining with the Chef - Chef Saito's Family recipe: MENCHI-KATSU",
            'description': 'md5:5aee4a9f9d81c26281862382103b0ea5',
            'timestamp': 1565965194,
            'upload_date': '20190816',
        },
    }, {
        # audio clip
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/audio/r_inventions-20201104-1/',
        'info_dict': {
            'id': 'r_inventions-20201104-1-en',
            'ext': 'm4a',
            'title': "Japan's Top Inventions - Miniature Video Cameras",
            'description': 'md5:07ea722bdbbb4936fdd360b6a480c25b',
        },
        'params': {
            # m3u8 download
            'skip_download': True,
        },
    }, {
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/video/2015173/',
        'only_matching': True,
    }, {
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/audio/plugin-20190404-1/',
        'only_matching': True,
    }, {
        'url': 'https://www3.nhk.or.jp/nhkworld/fr/ondemand/audio/plugin-20190404-1/',
        'only_matching': True,
    }, {
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/audio/j_art-20150903-1/',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        return self._extract_episode_info(url)


class NhkVodProgramIE(NhkBaseIE):
    _VALID_URL = r'%s/program%s(?P<id>[0-9a-z]+)(?:.+?\btype=(?P<episode_type>clip|(?:radio|tv)Episode))?' % (NhkBaseIE._BASE_URL_REGEX, NhkBaseIE._TYPE_REGEX)
    _TESTS = [{
        # video program episodes
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/program/video/japanrailway',
        'info_dict': {
            'id': 'japanrailway',
            'title': 'Japan Railway Journal',
        },
        'playlist_mincount': 1,
    }, {
        # video program clips
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/program/video/japanrailway/?type=clip',
        'info_dict': {
            'id': 'japanrailway',
            'title': 'Japan Railway Journal',
        },
        'playlist_mincount': 5,
    }, {
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/program/video/10yearshayaomiyazaki/',
        'only_matching': True,
    }, {
        # audio program
        'url': 'https://www3.nhk.or.jp/nhkworld/en/ondemand/program/audio/listener/',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        lang, m_type, program_id, episode_type = self._match_valid_url(url).groups()

        episodes = self._call_api(
            program_id, lang, m_type == 'video', False, episode_type == 'clip')

        entries = []
        for episode in episodes:
            episode_path = episode.get('url')
            if not episode_path:
                continue
            entries.append(self._extract_episode_info(
                urljoin(url, episode_path), episode))

        program_title = None
        if entries:
            program_title = entries[0].get('series')

        return self.playlist_result(entries, program_id, program_title)


# "bangumi" ("番組") means "program" in English (especially, TV program)
class NhkForSchoolBangumiIE(InfoExtractor):
    _VALID_URL = r'https?://www2\.nhk\.or\.jp/school/movie/(?P<type>bangumi|clip)\.cgi\?das_id=(?P<id>[a-zA-Z0-9_-]+)'
    _TESTS = [{
        'url': 'https://www2.nhk.or.jp/school/movie/bangumi.cgi?das_id=D0005150191_00000',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        program_type, video_id = self._match_valid_url(url).groups()

        webpage = self._download_webpage(
            'https://www2.nhk.or.jp/school/movie/%s.cgi?das_id=%s' % (program_type, video_id), video_id)

        # searches all assignments
        base_values = {g.group(1): g.group(2) for g in re.finditer(r'var\s+([a-zA-Z_]+)\s*=\s*"([^"]+?)";', webpage)}
        # and programObj values too
        program_values = {g.group(1): g.group(3) for g in re.finditer(r'(?:program|clip)Obj\.([a-zA-Z_]+)\s*=\s*(["\'])([^"]+?)\2;', webpage)}
        # extract all chapters
        chapter_durations = [parse_duration(g.group(1)) for g in re.finditer(r'chapterTime\.push\(\'([0-9:]+)\'\);', webpage)]
        chapter_titles = [('%s %s' % (g.group(1) or '', unescapeHTML(g.group(2)))).strip() for g in re.finditer(r'<div class="cpTitle"><span>(scene\s*\d+)?</span>([^<]+?)</div>', webpage)]

        # this is how player_core.js is actually doing (!)
        version = base_values.get('r_version') or program_values.get('version')
        if version:
            video_id = '%s_%s' % (video_id.split('_')[0], version)

        m3u8_url = 'https://nhks-vh.akamaihd.net/i/das/%s/%s_V_000.f4v/master.m3u8' % (video_id[0:8], video_id)
        formats = self._extract_m3u8_formats(
            m3u8_url, video_id, ext='mp4', m3u8_id='hls')
        self._sort_formats(formats)

        title = program_values['name']
        duration = parse_duration(base_values['r_duration'])
        upload_date = base_values['r_upload'].split('T')[0].replace('-', '')

        chapters = None
        if chapter_durations and chapter_titles and len(chapter_durations) == len(chapter_titles):
            start_time = chapter_durations
            end_time = chapter_durations[1:] + [duration]
            chapters = []
            for (s, e, t) in zip(start_time, end_time, chapter_titles):
                chapters.append({
                    'start_time': s,
                    'end_time': e,
                    'title': t,
                })

        return {
            'id': video_id,
            'title': title,
            'duration': duration,
            'upload_date': upload_date,
            'formats': formats,
            'chapters': chapters,
        }


class NhkForSchoolSubjectIE(InfoExtractor):
    IE_DESC = 'Portal page for each school subjects, like Japanese (kokugo, 国語) or math (sansuu/suugaku or 算数・数学)'
    KNOWN_SUBJECTS = (
        # 'path', # japanese, translation
        'rika',      # 理科      Science
        'syakai',    # 社会      Social Studies
        'kokugo',    # 国語      Japanese (primary language)
        'sansuu',    # 算数・数学 Mathematics
        'seikatsu',  # 生活      Living Environment Studies
        'doutoku',   # 道徳      Moral Education
        'ongaku',    # 音楽      Music
        'taiiku',    # 体育      Physical Education
        'zukou',     # 図工      Drawing and Crafts
        'gijutsu',   # 技術      Technical Arts (*1)
        'katei',     # 家庭      Home Economics (*1)
        'sougou',    # 総合      period for Integrated Study (see what it means: https://w.wiki/3Wdd )
        'eigo',      # 英語      English (1st foreign language)
        'tokkatsu',  # 特別活動   Special Activities
        'tokushi',   # 特別支援   "A class for special needs children"
        'sonota',    # その他 Miscellaneous
        # (*1): they are combined in real schools and called "技術家庭科" (gijutsu-katei-ka, Technical Arts and Home Economics)

        # translation ref. https://eigolab.net/1576
        # and https://eikaiwa.dmm.com/uknow/questions/75369/
        # and https://eikaiwa.dmm.com/uknow/questions/37210/
        # and https://eikaiwa.dmm.com/uknow/questions/37922/
        # and https://blog.goo.ne.jp/koji-kouritu-eigo/e/750ba2c137bca159c00bc7e89249b58d
    )
    _VALID_URL = r'https?://www\.nhk\.or\.jp/school/(?P<id>%s)' % (
        '|'.join(re.escape(s) for s in KNOWN_SUBJECTS)
    )

    _TESTS = [{
        'url': 'https://www.nhk.or.jp/school/sougou/',
        'info_dict': {
            'id': 'sougou',
            'title': '総合的な学習の時間',
        },
        'playlist_mincount': 16,  # as of 2021/06/20
    }, {
        'url': 'https://www.nhk.or.jp/school/rika/',
        'info_dict': {
            'id': 'rika',
            'title': '理科',
        },
        'playlist_mincount': 15,  # as of 2021/06/25
    }]

    @classmethod
    def suitable(cls, url):
        return super(NhkForSchoolSubjectIE, cls).suitable(url) and not NhkForSchoolProgramListIE.suitable(url)

    def _real_extract(self, url):
        subject_id = self._match_id(url)
        url = 'https://www.nhk.or.jp/school/%s/' % subject_id

        webpage = self._download_webpage(url, subject_id)
        programs = [g.group(1) for g in re.finditer(r'href="((?:https?://www\.nhk\.or\.jp)?/school/%s/[^/]+/")' % re.escape(subject_id), webpage)]
        title = self._search_regex(r'(?s)<span\s+class="subjectName">(.+?)</span>', webpage, 'title')
        title = clean_html(title)

        playlist = [self.url_result(urljoin(url, x)) for x in programs]
        return self.playlist_result(playlist, subject_id, title)


class NhkForSchoolProgramListIE(InfoExtractor):
    _VALID_URL = r'https?://www\.nhk\.or\.jp/school/(?P<id>(?:%s)/[a-zA-Z0-9_-]+)' % (
        '|'.join(re.escape(s) for s in NhkForSchoolSubjectIE.KNOWN_SUBJECTS)
    )
    _TESTS = [{
        'url': 'https://www.nhk.or.jp/school/sougou/q/',
        'info_dict': {
            'id': 'sougou/q',
            'title': 'Ｑ～こどものための哲学とは？',
        },
        'playlist_mincount': 20,  # as of 2021/06/20
    }]

    def _real_extract(self, url):
        program_id = self._match_id(url)

        webpage = self._download_webpage('https://www.nhk.or.jp/school/%s/' % program_id, program_id)

        title = self._html_search_regex(r'<h3>([^<]+?)</h3>', webpage, 'title', fatal=False)
        if not title:
            # both have format like "番組名 | NHK for School", so we have to strip last part
            _title = self._og_search_title(webpage) or self._html_extract_title(webpage)
            title = re.sub(r'\s*\|\s*NHK\s+for\s+School\s*$', '', _title)
        description = self._html_search_regex(
            r'(?s)<div\s+class="programDetail\s*">\s*<p>[^<]+</p>',
            webpage, 'description', fatal=False, group=0)

        bangumi_list = self._download_json(
            'https://www.nhk.or.jp/school/%s/meta/program.json' % program_id, program_id)
        # they're always bangumi
        bangumis = [self.url_result('https://www2.nhk.or.jp/school/movie/bangumi.cgi?das_id=' + x['part-video-dasid']) for x in bangumi_list['part']]

        return self.playlist_result(bangumis, program_id, title, description)
