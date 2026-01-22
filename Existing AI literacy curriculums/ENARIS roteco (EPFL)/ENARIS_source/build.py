# install required libraries:
#   pip install beautifulsoup4 css-html-js-minify htmlmin

import os, sys, re, shutil, warnings, json, itertools, operator, hashlib, glob
from bs4 import BeautifulSoup as BS, MarkupResemblesLocatorWarning, Comment
from css_html_js_minify import process_single_css_file
from htmlmin import minify

# ignore warning, text can look like anything
warnings.filterwarnings('ignore', category=MarkupResemblesLocatorWarning)

fileChangesFileName = 'filechanges.json'

rootdir = os.path.dirname(sys.argv[0])
datadir = rootdir + os.sep + 'data'
outputdir = rootdir + os.sep + 'output'
templatedir = rootdir + os.sep + 'templates'
assetdir = datadir + '/assets'
fileChanges = {}

try:
    with open(fileChangesFileName, 'r', encoding='utf-8') as json_file:
        fileChanges = json.load(json_file)
except FileNotFoundError:
    pass

def loadTemplate(m, templates):
    groups = list(filter(len, list(m.groups())))
    template = groups[0]
    # split, flatten and strip arguments
    groups = list(map(str.strip, itertools.chain(*map(operator.methodcaller('split', '|'), groups))))
    if not template in templates.keys():
        raise Exception('ERROR: template "%s" not found!'%template)
    content = templates[template]
    for i, arg in enumerate(groups):
        content = re.sub('{{\s*arg%s\s*}}'%i, arg, content)
    content = re.sub('{{\s*arg\d+\s*}}', '', content)
    return content

def parseTemplates(text, templates):
    text = re.sub('\[\[\s*([\w.]+)\s*\|?\s*(.*)\]\]', lambda m: loadTemplate(m, templates), text)
    return text

def parseVars(text, vars):
    for key, value in vars.items():
        text = re.sub('{{\s*%s\s*}}'%key, value, text)
    return text

def parseLang(text, lang):
    for l in ['en', 'de', 'hu']:
        if l == lang:
            # keep current language
            text = re.sub('{{\s*%s\s*:\s*([^}]*)}}'%l, r'\1', text)
        else:
            # strip other languages
            text = re.sub('{{\s*%s\s*:\s*[^}]*}}'%l, '', text)
    return text

def extractAbbreviations(match, abbr):
    lines = match.group().split('\n')
    lines.pop(0) # ignore first line
    lines.pop(-1) # ignore last line
    for line in lines:
        line = line.strip()
        if line :
            [key, value] = line.split(':')
            abbr[key.strip()] = value.strip()
    return ''

def extractReplacements(match, replacement):
    lines = match.group().split('\n')
    lines.pop(0) # ignore first line
    lines.pop(-1) # ignore last line
    for line in lines:
        [key, value] = line.split(':', 1)
        replacement[key.strip()] = value.strip()
    return ''

def replaceSpaces(match):
    return match.group().replace(' ', '%20')

def parseHTML(text, cssfiles):
    abbr = {}
    replace = {}
    text = re.sub('{\[[ \w]*\r?\n(\s*\w+\s*:\s*[\s\w]+\r?\n)+\w*\]}', lambda m: extractAbbreviations(m, abbr), text)
    text = re.sub('\[{[ \w]*\r?\n(\s*\w+\s*:\s*[^\n]+\r?\n)+\w*}\]', lambda m: extractReplacements(m, replace), text)
    text = re.sub('(href|src)\w*=\w*["\']([^"\']+)["\']', lambda m: replaceSpaces(m), text)
    for file in cssfiles.items():
        text = text.replace(f'/{file[0]}"', f'/{file[1]}"')
    html = BS(text, 'html.parser')

    # remove comments
    for element in html(text=lambda text: isinstance(text, Comment)):
        element.extract()

    if abbr or replace:
        ps = html.select('main p, main dd, main li, main td, main em, main strong, main span')
        for p in ps:
            for child in p.contents:
                if child.name == None: # basic text element
                    txt = str(child)
                    for key, value in abbr.items():
                        txt = re.sub(key, '<abbr title="%s">%s</abbr>'%(value, key), txt)
                    for key, value in replace.items():
                        txt = re.sub(key, value, txt)
                    child.replace_with(BS(txt, 'html.parser'))
    
    return str(html)

templates = {}
for dirpath, folders, files in os.walk(templatedir):
    for file in files:
        f = open(dirpath + os.sep + file, 'r', encoding='utf-8')
        templates[file] = f.read()

templatechanged = False
for dirpath, folders, files in os.walk(templatedir):
    relativepath = dirpath.replace(templatedir, '')
    for file in files:
        filepath = relativepath + os.sep + file
        modified = os.path.getmtime(templatedir + filepath)
        if filepath not in fileChanges or fileChanges[filepath] < modified:
            fileChanges[filepath] = modified
            templatechanged = True

cssfiles = {}
for dirpath, folders, files in os.walk(assetdir):
    for file in files:
        if file.endswith('.css'):
            f = open(dirpath + os.sep + file, 'r', encoding='utf-8')
            hash = hashlib.sha256(f.read().encode('utf-8')).hexdigest()[:6]
            cssfiles[file] = file[:-4] + f'.{hash}.css'
            filepath = relativepath + os.sep + file
            modified = os.path.getmtime(assetdir + filepath)
            if filepath not in fileChanges or fileChanges[filepath] < modified:
                fileChanges[filepath] = modified
                templatechanged = True

numfiles = 0
for dirpath, folders, files in os.walk(datadir):
    relativepath = dirpath.replace(datadir, '')
    vars = {
        'root': '/'.join(['..'] * relativepath.count(os.sep) or ['.']),
        'lang': (re.findall('^[\\\\/](de|hu|en)[\\\\/]?', relativepath) or ['en'])[0],
    }
    vars['lname'] = {'en': 'English', 'de': 'Deutsch', 'hu': 'Magyar'}[vars['lang']]
    vars['assets'] = vars['root'] + '/assets'

    
    for file in files:
        filepath = relativepath + os.sep + file
        modified = os.path.getmtime(datadir + filepath)
        if file.endswith('.html'):
            if (templatechanged) or (filepath not in fileChanges) or (fileChanges[filepath] < modified):
                fileChanges[filepath] = modified

                backlink = '../'
                # adapt backlinks (top level and subfolder)
                if file.endswith(('methods.html', 'education.html')):
                    backlink = './'
                if any(x in relativepath for x in [os.sep+'Exercises'+os.sep, os.sep+'Slides'+os.sep]):
                    backlink += '../'
                vars['back'] = backlink + 'index.html'
                vars['pdf'] = relativepath.split(os.sep)[-1] + '.pdf'

                # top level pdf links
                if vars['pdf'] in ['en.pdf', 'de.pdf', 'hu.pdf']:
                    if file == 'index.html':
                        vars['pdf'] = 'Material.pdf'
                    elif file == 'methods.html':
                        vars['pdf'] = 'Methods.pdf'
                    elif file == 'education.html':
                        vars['pdf'] = 'Education.pdf'

                # language switch links
                for lang, lname in [('en', 'English'), ('de', 'Deutsch'), ('hu', 'Magyar')]:
                    filepath_lang = filepath.replace(os.sep + vars['lang'] + os.sep, '/' + lang + '/').replace(os.sep, '/')
                    if os.path.exists(datadir + filepath_lang):
                        if lang != vars['lang']:
                            vars['switch_' + lang] = '<li><a href="' + vars['root'] + filepath_lang + '"><img src="' + vars['root'] + '/assets/icon/' + lang + '.png" class="lang" alt="' + lname + '" title="' + lname + '"/></a></li>'
                        else:
                            vars['switch_' + lang] = ''
                    else:
                        vars['switch_' + lang] = ''
                        print('skipping lang option \'' + lang + '\' - no file:' + filepath_lang)
                
                # image path
                img_path = vars['assets']
                module = re.findall('^[\\\\/](de|hu|en)[\\\\/]([^\\\\/]+)', relativepath)
                if len(module) and len(module[0]) == 2:
                    img_path += '/modules/' + module[0][1]
                vars['images'] = img_path
                
                numfiles+=1
                print('create file: ' + filepath)
                with open(datadir + filepath, 'r', encoding='utf-8') as fin:
                    content = fin.read()
                    content = parseTemplates(content, templates)
                    content = parseVars(content, vars)
                    content = parseLang(content, vars['lang'])
                    content = parseHTML(content, cssfiles)
                    content = minify(content)
                    os.makedirs(outputdir + relativepath, exist_ok=True)
                    with open(outputdir + filepath, 'w', encoding='utf-8') as fout:
                        fout.write(content)
        elif (filepath not in fileChanges) or (fileChanges[filepath] < modified):
            newfilepath = filepath
            if file.endswith('.css'):
                newfilepath = filepath.replace(file, cssfiles[file])
                files = glob.glob(f'{outputdir + filepath[:-4]}*.css')
                for file in files:
                    os.remove(file)
            fileChanges[filepath] = modified
            numfiles+=1
            print('copy file: ' + newfilepath)
            os.makedirs(outputdir + relativepath, exist_ok=True)
            shutil.copy(datadir + filepath, outputdir + newfilepath)
            if file.endswith('.css') and not ".min." in file:
                process_single_css_file(outputdir + newfilepath, overwrite=True)

print('%s files modified' % numfiles)

with open(fileChangesFileName, 'w') as outfile:
    json.dump(fileChanges, outfile)