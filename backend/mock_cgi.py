import urllib.parse

def parse_qs(qs, keep_blank_values=False, strict_parsing=False, encoding='utf-8', errors='replace'):
    return urllib.parse.parse_qs(qs, keep_blank_values, strict_parsing, encoding, errors)

def parse_multipart(fp, pdict, encoding='utf-8', errors='replace', separator=b'', buffer_size=8192, max_headers=100):
    return {}, {}

def parse_header(line):
    return '', {}

def escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')