"""Les en-têtes envoyés aux sites ne doivent annoncer que des encodages que
`requests` sait décoder. « br » (brotli) sans paquet brotli rendait du binaire
illisible : LAMSADE, HEC IA, IRIS, Jean-Jaurès… paraissaient « sans cartes »."""

import importlib.util

import scrape


def _supported(encoding):
    if encoding == "br":
        return any(importlib.util.find_spec(m) for m in ("brotli", "brotlicffi"))
    return encoding in ("gzip", "deflate", "identity")


def test_accept_encoding_only_lists_decodable_codecs():
    offered = [e.split(";")[0].strip() for e in scrape.CDF_HEADERS["Accept-Encoding"].split(",")]
    assert all(_supported(e) for e in offered), offered
