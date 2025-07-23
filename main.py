import asyncio
import logging
import os
import re
from asyncio import Queue, TaskGroup
from pathlib import Path, PurePath

import aiofiles
import aiofiles.os
import httpx
import yaml
from bs4 import BeautifulSoup
from slugify import slugify

from mdconverter import TableConverter

logging.basicConfig(level=logging.INFO)

CONCURRENCY = 4

class UnseenLinkError(KeyError):
    pass

def url_replace_leaf(url: httpx.URL, new_leaf: str) -> httpx.URL:
    return url.copy_with(path=str(PurePath(url.path).parent.joinpath(new_leaf)))

def listify_dict(d: dict) -> list:
    result = []

    capitalized = {
        "DTC", "OBD", "VIN", "EGR", "PCV", "LF", "MAF", "IAT", "CPP", "PSP", "ECT", "PCM", "CKP", "CMP", "TP", "APP",
        "HO2S", "MAP", "KS", "BARO", "SST", "ABS", "DSC", "HU", "CM", "VSS", "TR", "ATF", "KOEO", "KOER", "PID", "CD",
        "MP3", "AudioPilot", "ALC", "BOSE", "MIL", "AT", "MT", "WM", "SJ6A", "EL", "ESA", "EVAP", "OCV"
    }

    for key, value in d.items():
        key = key.title()

        for cap in capitalized:
            key = re.sub(rf"{cap.capitalize()}(\W)", rf"{cap}\g<1>", key)

        if isinstance(value, dict):
            result.append({
                key: listify_dict(value)
            })
        else:
            result.append({
                key: value
            })

    return result

class WSMMarkdownConverter(TableConverter):
    def __init__(self, article_map: dict[str, str], nav: dict, breadcrumbs: list[str], filename: str, **kwargs):
        super().__init__(keep_inline_images_in=['td'], **kwargs)
        self.article_map = article_map
        self.nav = nav
        self.breadcrumbs = breadcrumbs
        self.filename = filename
        self.path = PurePath(self.article_map[self.filename]).parent

    def convert_dd(self, el, text, parent_tags):
        return text.strip()

    def convert_title(self, el, text, parent_tags):
        return ''

    def convert_a(self, el, text, parent_tags):
        if href := el.get('href'):
            if not href.startswith('#'):
                href = href.lstrip('.').lstrip('/')
                fragment = f"#{href.split('#')[1]}" if '#' in href else ''
                href = href.split('#')[0].replace('.html', '.md')
                if href in self.article_map:
                    prefix = ''
                    path = self.path
                    while not PurePath(self.article_map[href]).is_relative_to(path):
                        prefix += '../'
                        path = path.parent
                    el.attrs['href'] = prefix + str(PurePath(self.article_map[href]).relative_to(path)) + fragment
                    # if 'table' in parent_tags:
                    #     # The extra `../` is MkDocs-specific, and actually breaks viewing Markdown locally!
                    #     el.attrs['href'] = '../' + el.attrs['href'].replace('.md', '')
                else:
                    raise UnseenLinkError(href)
            return super().convert_a(el, text, parent_tags)
        elif name := el.get('name'):
            return super().convert_a(el, f'<a name="{name}"></a>{text}', parent_tags)
        else:
            raise NotImplementedError(f"What kind of anchor is this!? Check {self.filename}...")

    def convert_img(self, el, text, parent_tags):
        src = el.get('src')
        if src:
            # Calculate the relative path to the `images/` folder
            el.attrs['src'] = '../' * len(self.path.parts) + 'images/' + PurePath(src).name
            # if 'table' in parent_tags:
            #     # The extra `../` is MkDocs-specific, and actually breaks viewing Markdown locally!
            #     el.attrs['src'] = '../' + el.attrs['src']
        return super().convert_img(el, text, parent_tags)

    def convert(self, html):
        title = ''
        leaf = self.nav
        parents = len(self.breadcrumbs)
        for part in self.breadcrumbs:
            leaf = leaf[part]
            filename = '../' * parents
            if isinstance(leaf, str):
                filename += leaf
            elif isinstance(leaf, dict):
                if 'INDEX' not in leaf:
                    raise UnseenLinkError()
                filename += leaf['INDEX']
            title += ' ➭ ' + f"[{part}]({filename})"
        return title.removeprefix(' ➭ ') + '\n\n' + super().convert(html)

class WSMScraper:
    def __init__(self, wsm_id="D933-1A-22C_Ver26"):
        self.wsm_id = wsm_id
        self.base_uri = f"/wsm-secure/WSM/{self.wsm_id}/"
        self.start_url = "https://mazdamanuals.com.au" + self.base_uri
        self.session = httpx.AsyncClient(headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:140.0) Gecko/20100101 Firefox/140.0"
        },
        follow_redirects=True)
        self.seen = set()
        self.article_map: dict[str, str] = {}
        self.nav: dict = {}
        self.md_queue = Queue()

    async def markdownify(self, breadcrumbs: list[str], filename: Path, content: bytes, retries: int = CONCURRENCY + 1):
        try:
            logging.debug(breadcrumbs)
            location = '/'.join(slugify(part) for part in breadcrumbs)
            self.article_map[filename.name] = location + '/' + filename.name
            logging.debug(location)

            match filename.suffix:
                case ".md":
                    leaf = self.nav
                    parent = leaf
                    part = None
                    for part in breadcrumbs:
                        if not part in leaf:
                            leaf[part] = {}
                        parent = leaf
                        leaf = leaf[part]
                    if not filename.name.startswith("left_menu") and not filename.name.startswith("node"):
                        # This is needed for some edge cases where the ToC contains two different links with the same name
                        while part in parent and isinstance(parent[part], str) and parent[part] != location + '/' + filename.name:
                            part = part + ' '
                        parent[part] = location + '/' + filename.name
                    else:
                        if not parent[part] or 'INDEX' not in parent[part]:
                            parent[part]["INDEX"] = location + '/' + filename.name
                    content = WSMMarkdownConverter(self.article_map, self.nav, breadcrumbs, filename.name).convert(content).encode("utf-8")
                    filename = Path(self.wsm_id).joinpath("docs").joinpath(location).joinpath(filename.name).with_suffix(
                        ".md")
                case ".png":
                    filename = Path(self.wsm_id).joinpath("docs").joinpath("images").joinpath(filename.name).with_suffix(".png")
                case ".pdf":
                    filename = Path(self.wsm_id).joinpath("docs").joinpath("pdf").joinpath(filename.name).with_suffix(".pdf")
                    self.article_map["javascript:Open()"] = self.article_map[filename.name]
                case _:
                    raise NotImplementedError(f"Unsupported filename: {filename}")

            if filename.exists() and not os.environ.get("FORCE_MARKDOWN", False):
                return

            await aiofiles.os.makedirs(os.path.dirname(filename), exist_ok=True)
            async with aiofiles.open(filename, "wb") as f:
                logging.info(f"Writing docs: {filename}")
                await f.write(content)
        except UnseenLinkError as e:
            # This happens if the file contains links to other files that haven't been processed yet. We need to
            # enqueue another call to `markdownify` with the same parameters - by the time it's called, the missing
            # links should have been processed already.
            if retries > 0:
                await self.md_queue.put(self.markdownify(breadcrumbs, filename, content, retries - 1))
            else:
                logging.error(f"Couldn't figure out the link {e} while processing {filename.name}")
        finally:
            self.md_queue.task_done()

    async def download(self, url: httpx.URL) -> (Path, bytes):
        filename = Path(self.wsm_id).joinpath(url.path.replace(self.base_uri, ''))

        if filename in self.seen:
            return None, None

        self.seen.add(filename)

        if filename.is_absolute():
            raise PermissionError("Absolute paths are not allowed")

        if filename.exists():
            async with aiofiles.open(filename, "rb") as f:
                logging.debug(f"Reading cached: {filename}")
                content = await f.read()
        else:
            logging.info(f"Downloading: {url}")
            response = await self.session.get(url)
            await aiofiles.os.makedirs(os.path.dirname(filename), exist_ok=True)
            async with aiofiles.open(filename, "wb") as f:
                logging.debug(f"Caching: {url}")
                await f.write(response.content)
            content = response.content

        return filename, content

    async def parse_page(self, url: httpx.URL, breadcrumbs: list[str]):
        filename, page_content = await self.download(url)

        if page_content is None:
            return

        soup = BeautifulSoup(page_content, "html.parser")

        for item in soup.find_all("img"):
            img_filename, img_content = await self.download(url_replace_leaf(url, item.attrs["src"]))
            if img_filename is not None and img_content is not None:
                await self.md_queue.put(self.markdownify(breadcrumbs, img_filename, img_content))

        for item in soup.find_all("a", href=True, limit=200):
            if item.attrs["href"] == "javascript:Open()":
                for line in soup.script.text.splitlines():
                    line = line.strip()
                    if match := re.match(r"var pdfname\s+=\s+'(.*?)'", line):
                        pdf_filename, pdf_content = await self.download(url_replace_leaf(url, f"../pdf/{match.group(1)}"))
                        if pdf_filename is not None and pdf_content is not None:
                            await self.md_queue.put(self.markdownify(["pdf"], pdf_filename, pdf_content))
                        break
            if "target" in item.attrs:
                if item.attrs["target"] in ("main", "fraToc"):
                    await self.parse_page(
                        url_replace_leaf(url, item.attrs["href"]),
                        breadcrumbs + [item.text]
                    )

        await self.md_queue.put(self.markdownify(breadcrumbs, filename.with_suffix('.md'), page_content))

    async def worker(self):
        while not self.md_queue.empty():
            task = await self.md_queue.get()
            await task

    async def scrape(self):
        response = await self.session.get(self.start_url)
        index = BeautifulSoup(response.text, "html.parser")

        main_menu_src = index.find("frame", attrs={"name": "main_menu"}).attrs["src"]
        response = await self.session.get(self.start_url + main_menu_src)
        main_menu_soup = BeautifulSoup(response.text, "html.parser")
        model = main_menu_soup.find("font", color="#ffffff").text

        srvc_menu_src = index.find("frame", attrs={"name": "srvc_menu"}).attrs["src"]
        response = await self.session.get(self.start_url + srvc_menu_src)
        srvc_menu_soup = BeautifulSoup(response.text, "html.parser")

        left_menu_list = []
        default_file_list = []
        for line in srvc_menu_soup.script.text.splitlines():
            line = line.strip()
            if match := re.match(r'^LeftMenuList\[\d+]\s+=\s+"(.*?)";$', line):
                left_menu_list.append(match.group(1))
            elif match := re.match(r'^DefaultFileList\[\d+]\s+=\s+"(.*?)";$', line):
                default_file_list.append(match.group(1))

        for title, src in zip(srvc_menu_soup.find_all("option"), left_menu_list):
            await self.md_queue.put(self.parse_page(url_replace_leaf(response.url, src), [title.text]))

        async with TaskGroup() as group:
            for i in range(CONCURRENCY):
                group.create_task(self.worker())

        mkdocs = {
            "markdown_extensions": [
                "sane_lists",
                "attr_list",
                "grids"
            ],
            "site_name": f"Mazda WSM // {model} ({self.wsm_id})",
            "nav": listify_dict(self.nav),
            "theme": {
                "name": "terminal",
                "features": [
                    "navigation.side.indexes"
                ]
            }
        }
        with open(f"{self.wsm_id}/mkdocs.yml", "w") as outfile:
            yaml.dump(mkdocs, outfile)

if __name__ == "__main__":
    scraper = WSMScraper()
    asyncio.run(scraper.scrape())