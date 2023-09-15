import base64
import os
import pathlib

from atlassian import Confluence
from urllib import parse

FORBIDDEN_CHARACTERS = r'\/:*"<>|?'
ROOT_URL = ''
CONFLUENCE_URL = ''
USERNAME = ''
PASSWORD = ''
DIR_DOWNLOAD = ''

confluence = Confluence(
    url=CONFLUENCE_URL,
    username='',
    password='',
)


def sanitize_filename(filename: str) -> str:
    for char in FORBIDDEN_CHARACTERS:
        filename = filename.replace(char, ' ')

    return filename


def extract_page_id_from_confluence_url(url: str) -> int:
    if 'pageId' in url:
        # regular links
        page_id = parse.parse_qs(parse.urlparse(url).query)['pageId'][0]
        return int(page_id)

    path = parse.urlparse(url).path

    if path.startswith('/x/'):
        # short links
        # https://community.atlassian.com/t5/Confluence-questions/Re-What-is-the-algorithm-used-to-create-the-quot-Tiny-links-quot/qaq-p/1149303/comment-id/150363#M150363

        tiny = path.split('/')[-1]
        return int.from_bytes(
            base64.b64decode(tiny.ljust(8, 'A').replace('_', '+').replace('-', '/').encode()),
            byteorder='little',
        )

    if path.startswith('/display/'):
        # links with page name
        space, title = path.split('/')[-2:]
        title = parse.unquote_plus(title)

        page_id = confluence.get_page_id(space, title)
        return page_id

    raise ValueError('Bad Confluence link')


def copy_files(
        page_id: int,
        parent_path: str = '',
) -> tuple[list[str], list[str]]:
    page = confluence.get_page_by_id(page_id)
    title = sanitize_filename(page['title'])

    self_path = os.path.join(parent_path, title)

    children = confluence.get_page_child_by_type(page_id, type='page')

    children_exists = False
    files_to_create = []
    exceptions = []

    for child in children:
        children_exists = True
        child_files_to_create, child_exceptions = copy_files(
            page_id=child['id'],
            parent_path=self_path,
        )
        files_to_create.extend(child_files_to_create)
        exceptions.extend(child_exceptions)

    if children_exists:
        return files_to_create, exceptions

    page_pdf = confluence.get_page_as_word(page_id)

    filename = f'{title}.doc'
    full_path = os.path.join(
        os.getcwd(),
        DIR_DOWNLOAD,
        parent_path,
    )

    pathlib.Path(full_path) \
        .mkdir(parents=True, exist_ok=True)
    filename = os.path.join(full_path, filename)

    with open(filename, 'wb') as output:
        output.write(page_pdf)

    return [filename], []


def create_files_from_confluence():
    root_id = extract_page_id_from_confluence_url(ROOT_URL)

    files_to_create, exceptions = copy_files(
        page_id=root_id,
    )
