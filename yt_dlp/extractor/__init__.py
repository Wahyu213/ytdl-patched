import os

from ..utils import load_plugins

from typing import TYPE_CHECKING, List, Type
if TYPE_CHECKING:
    from .common import SelfHostedInfoExtractor

_LAZY_LOADER = False
if not os.environ.get('YTDLP_NO_LAZY_EXTRACTORS'):
    try:
        from .lazy_extractors import *
        from .lazy_extractors import _ALL_CLASSES
        _SELFHOSTED_CLASSES = []
        _LAZY_LOADER = True
    except ImportError:
        pass

if not _LAZY_LOADER:
    from .extractors import *
    _ALL_CLASSES = [
        klass
        for name, klass in globals().items()
        if name.endswith('IE') and name not in ('GenericIE', 'StreamlinkIE')
    ]
    _SELFHOSTED_CLASSES = [
        ie for ie in _ALL_CLASSES if ie._SELF_HOSTED
    ]
    _ALL_CLASSES.append(GenericIE)

_PLUGIN_CLASSES = load_plugins('extractor', 'IE', globals())
_ALL_CLASSES = list(_PLUGIN_CLASSES.values()) + _ALL_CLASSES


def gen_extractor_classes():
    """ Return a list of supported extractors.
    The order does matter; the first extractor matched is the one handling the URL.
    """
    return _ALL_CLASSES


def gen_selfhosted_extractor_classes() -> List[Type['SelfHostedInfoExtractor']]:
    """
    Return a list of extractors for self-hosted services.
    """
    return _SELFHOSTED_CLASSES


def gen_extractors():
    """ Return a list of an instance of every supported extractor.
    The order does matter; the first extractor matched is the one handling the URL.
    """
    return [klass() for klass in gen_extractor_classes()]


def list_extractors(age_limit):
    """
    Return a list of extractors that are suitable for the given age,
    sorted by extractor ID.
    """

    return sorted(
        filter(lambda ie: ie.is_suitable(age_limit), gen_extractors()),
        key=lambda ie: ie.IE_NAME.lower())


def get_info_extractor(ie_name):
    """Returns the info extractor class with the given ie_name"""
    return globals()[ie_name + 'IE']
