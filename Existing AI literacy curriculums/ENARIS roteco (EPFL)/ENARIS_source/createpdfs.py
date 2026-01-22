import subprocess, os, sys, shutil, re

chrome_bins = [
    # linux
    'google-chrome',
    'google-chrome-stable',
    'chrome',
    'chromium-browser',
    # windows
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
]
chrome_bin = None
for bin in chrome_bins:
    chrome_bin = shutil.which(bin)
    if chrome_bin:
        break

if chrome_bin:
    rootdir = os.path.dirname(sys.argv[0])
    indir = rootdir + os.sep + 'output'
    outdir = rootdir + os.sep + 'output'

    infile = rootdir + '/output/en/index.html'
    outfile = rootdir + '/test.pdf'

    for dirpath, folders, files in os.walk(indir):
        relativepath = dirpath.replace(indir, '')
        for file in files:
            filepath = relativepath + os.sep + file
            modified = os.path.getmtime(indir + filepath)
            if file.endswith('.html'):
                match = re.findall('[\\\\/]([^\\\\/]+)[\\\\/](index|methods|education)\.html$', filepath)
                if match:
                    infile = indir + filepath
                    dirname = match[0][0]
                    filename = dirname + '.pdf'
                    if match[0][1] == 'methods':
                        filename = 'Methods.pdf'
                    elif match[0][1] == 'education':
                        filename = 'Education.pdf'
                    elif dirname in ('en', 'de', 'hu'):
                        filename = 'Material.pdf'
                    outfile = outdir + filepath.replace(file, '') + filename

                    subprocess.call(f'"{chrome_bin}" --headless --disable-gpu --run-all-compositor-stages-before-draw --print-to-pdf-no-header --virtual-time-budget=10000 --print-to-pdf="{outfile}" "{infile}"', shell=True)
                    print('created file: ' + outfile.replace(outdir, ''))
else:
    print('Google chrome not found!')


