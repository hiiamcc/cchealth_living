"""Generate a review-only HTML preview from Notion, without modifying published site files."""
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[0]
SITE = 'https://hiiamcc.github.io/cchealth_living/'
API = 'https://api.notion.com/v1/'
TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = os.environ['NOTION_DATABASE_ID']
HEADERS = {'Authorization': 'Bearer '+TOKEN, 'Notion-Version':'2022-06-28','Content-Type':'application/json'}


def get(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, headers=HEADERS, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def pages():
    out=[]; cursor=None
    while True:
        data={'page_size':100}
        if cursor: data['start_cursor']=cursor
        res=get(API+'databases/'+DATABASE_ID+'/query',data)
        out.extend(res['results'])
        if not res.get('has_more'): return out
        cursor=res.get('next_cursor')
        if not cursor: raise RuntimeError('Missing database pagination cursor')


def blocks(parent):
    out=[]; cursor=None
    while True:
        q={'page_size':100}
        if cursor: q['start_cursor']=cursor
        res=get(API+'blocks/'+parent+'/children?'+urllib.parse.urlencode(q))
        out.extend(res['results'])
        if not res.get('has_more'): return out
        cursor=res.get('next_cursor')
        if not cursor: raise RuntimeError('Missing block pagination cursor')


def plain(prop):
    if not prop: return ''
    typ=prop.get('type','')
    if typ in ('title','rich_text'):
        return ''.join(x.get('plain_text','') for x in prop.get(typ,[]))
    if typ in ('select','status'):
        return (prop.get(typ) or {}).get('name','')
    if typ=='url': return prop.get('url') or ''
    return ''


def rich(items):
    output=[]
    for x in items or []:
        val=html.escape(x.get('plain_text',''))
        ann=x.get('annotations') or {}
        if ann.get('code'): val='<code>'+val+'</code>'
        if ann.get('bold'): val='<strong>'+val+'</strong>'
        if ann.get('italic'): val='<em>'+val+'</em>'
        if ann.get('strikethrough'): val='<s>'+val+'</s>'
        if ann.get('underline'): val='<u>'+val+'</u>'
        url=(x.get('href') or '')
        if url.startswith(('https://','http://')):
            val='<a href="'+html.escape(url,quote=True)+'" rel="noopener noreferrer" target="_blank">'+val+'</a>'
        output.append(val)
    return ''.join(output)


def render_block(b):
    t=b.get('type','')
    obj=b.get(t) or {}
    txt=rich(obj.get('rich_text',[]))
    if t in ('paragraph','heading_1','heading_2','heading_3','quote'):
        tag={'paragraph':'p','heading_1':'h2','heading_2':'h2','heading_3':'h3','quote':'blockquote'}[t]
        body=f'<{tag}>{txt}</{tag}>'
    elif t in ('bulleted_list_item','numbered_list_item'):
        body=f'<li>{txt}</li>'
    elif t=='divider': body='<hr>'
    elif t=='image':
        src=(obj.get('external') or obj.get('file') or {}).get('url','')
        # Notion-hosted file URLs expire; do not silently embed broken links.
        if obj.get('file'):
            raise RuntimeError('文章包含 Notion 上傳圖片：需先建立圖片保存機制，避免預覽連結過期。')
        if not src.startswith('https://'): raise RuntimeError('Unsupported image URL')
        caption=rich(obj.get('caption',[]))
        body='<figure><img loading="lazy" style="max-width:100%;height:auto" src="'+html.escape(src,quote=True)+'" alt=""><figcaption>'+caption+'</figcaption></figure>'
    elif t in ('bookmark','embed','video'):
        url=obj.get('url') or (obj.get('external') or {}).get('url','')
        if not url.startswith(('https://','http://')): raise RuntimeError('Unsupported embedded URL')
        body='<p><a href="'+html.escape(url,quote=True)+'" target="_blank" rel="noopener noreferrer">'+html.escape(url)+'</a></p>'
    elif t in ('callout','toggle'):
        body='<div class="notion-callout"><p>'+txt+'</p></div>'
    elif t=='to_do': body='<p>☑ ' + txt + '</p>' if obj.get('checked') else '<p>☐ '+txt+'</p>'
    else:
        raise RuntimeError('尚未支援 Notion 區塊類型：'+t+'。為避免漏掉內容，已停止產生預覽。')
    if b.get('has_children'):
        children=render_children(blocks(b['id']))
        if t in ('bulleted_list_item','numbered_list_item'):
            body=body[:-5]+children+'</li>'
        else: body+=children
    return body


def render_children(items):
    result=[]; current=None
    for b in items:
        t=b.get('type')
        list_tag={'bulleted_list_item':'ul','numbered_list_item':'ol'}.get(t)
        if current!=list_tag:
            if current: result.append('</'+current+'>')
            if list_tag: result.append('<'+list_tag+'>')
            current=list_tag
        result.append(render_block(b))
    if current: result.append('</'+current+'>')
    return '\n'.join(result)


def youtube_embed(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.hostname in ('youtu.be','www.youtu.be'):
        video_id=parsed.path.strip('/')
    elif parsed.hostname in ('youtube.com','www.youtube.com','m.youtube.com'):
        video_id=urllib.parse.parse_qs(parsed.query).get('v',[''])[0]
        if parsed.path.startswith('/shorts/') or parsed.path.startswith('/embed/'):
            video_id=parsed.path.split('/')[2]
    else: return ''
    return 'https://www.youtube-nocookie.com/embed/'+video_id if re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id) else ''


def main():
    template_path=ROOT/'article-template.html'
    if not template_path.exists(): raise RuntimeError('找不到 article-template.html')
    template=template_path.read_text(encoding='utf-8')
    outdir=ROOT/'preview-output'
    outdir.mkdir(exist_ok=True)
    count=0
    for page in pages():
        props=page['properties']
        status=plain(props.get('發布狀態'))
        if status!='待審核': continue
        title=plain(props.get('文章標題'))
        summary=plain(props.get('文章摘要'))
        category=plain(props.get('文章分類'))
        slug=plain(props.get('文章網址代稱'))
        video=plain(props.get('YouTube 網址'))
        if not title or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug):
            raise RuntimeError('待審核文章缺少標題或網址代稱格式不正確')
        source_blocks=blocks(page['id'])
        if not source_blocks: raise RuntimeError('待審核文章沒有內文：'+slug)
        body=render_children(source_blocks)
        soup=BeautifulSoup(template,'html.parser')
        article=soup.select_one('article.art-page')
        prose=soup.select_one('article .prose')
        head=soup.select_one('article .art-head')
        if not article or not prose or not head: raise RuntimeError('文章模板缺少必要元素')
        article['id']=slug
        h1=head.find('h1'); h1.clear(); h1.append(title)
        p=head.find('p'); p.clear(); p.append(summary)
        badge=head.select_one('.badge')
        if badge: badge.string=category or '健康知識'
        for child in list(prose.contents): child.extract()
        for child in BeautifulSoup(body,'html.parser').contents: prose.append(child)
        soup.title.string=title+'｜多C多健康｜預覽'
        desc=soup.find('meta',attrs={'name':'description'})
        if desc: desc['content']=summary
        for meta in soup.find_all('meta',attrs={'property':True}):
            if meta['property']=='og:title': meta['content']=title
            if meta['property']=='og:description': meta['content']=summary
        canonical=soup.find('link',rel='canonical')
        if canonical: canonical.decompose()
        noindex=soup.new_tag('meta');noindex.attrs={'name':'robots','content':'noindex,nofollow,noarchive'}
        soup.head.append(noindex)
        # Preview is opened locally or in an Actions artifact, so absolute links are required.
        for a in soup.find_all('a',href=True):
            if a['href'].startswith('../../index.html'):
                a['href']=SITE+a['href'][len('../../index.html'):]
        wrap=soup.select_one('.video-wrap')
        if wrap:
            embed=youtube_embed(video)
            if embed:
                frame=wrap.find('iframe')
                if frame: frame['src']=embed; frame['title']=title
                anchor=wrap.find('a',href=True)
                if anchor: anchor['href']=video
            else: wrap.decompose()
        banner=soup.new_tag('div')
        banner['style']='position:sticky;top:0;z-index:9999;background:#FFF2AE;color:#493332;padding:10px;text-align:center;font-weight:bold;border-bottom:2px solid #FF7F68'
        banner.string='僅供審核的預覽版本｜尚未發布到正式網站'
        soup.body.insert(0,banner)
        dest=outdir/(slug+'.html')
        dest.write_text(str(soup),encoding='utf-8')
        count+=1
        print('預覽完成：'+slug+'（'+str(len(source_blocks))+' 個第一層區塊）')
    if count==0: print('目前沒有待審核文章')
    print('預覽檔案數：',count)

if __name__=='__main__': main()
