from markdown import markdown

from mdconverter import TableConverter

# FILENAME = "wsm/D933-1A-22C_Ver26/esicont/srvc/html/id075000800100.html"
# FILENAME = "wsm/D933-1A-22C_Ver26/esicont/mission/B30/html/id000000810000.html"
# FILENAME = "wsm/D933-1A-22C_Ver26/esicont/srvc/html/id031100100200.html"
# FILENAME = "wsm/D933-1A-22C_Ver26/esicont/srvc/html/id051400255600.html"
FILENAME = "wsm/D933-1A-22C_Ver26/esicont/srvc/html/id021100800200.html"
# FILENAME = "wsm/D933-1A-22C_Ver26/esicont/srvc/html/id092200100900.html"

if __name__ == '__main__':
    tc = TableConverter(keep_inline_images_in=['td'])
    md = tc.convert(open(FILENAME, 'rt').read())
    print(md)
    html = markdown(md, extensions=['grids', 'attr_list', 'def_list', 'sane_lists'])
