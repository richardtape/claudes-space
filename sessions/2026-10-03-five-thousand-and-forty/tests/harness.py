"""Inject an interaction script into index.html and run it in headless Chrome.
usage: python3 tests/harness.py SCRATCHDIR"""
import sys, subprocess, json, html, re, pathlib
SP = pathlib.Path(sys.argv[1]); HERE = pathlib.Path(__file__).parent.parent
s = (HERE / 'index.html').read_text()
harness = r"""<script>
window.__log=[];window.addEventListener('error',e=>__log.push('ERR '+e.message+' @'+e.lineno));
window.addEventListener('load',()=>{
 const $=id=>document.getElementById(id), L=m=>__log.push(m);
 setTimeout(()=>{
  $('t357').click(); L('357: count='+$('tCount').textContent+' info='+$('tInfo').textContent);
  $('tClear').click(); L('clear: count='+$('tCount').textContent);
  const dots=[...document.querySelectorAll('#qboard .dot')];
  dots[0].dispatchEvent(new Event('click')); L('dot0: '+$('tCount').textContent+' | '+$('tMsg').textContent);
  dots[17].dispatchEvent(new Event('click')); L('dot17: '+$('tCount').textContent+' | '+$('tMsg').textContent);
  dots[0].dispatchEvent(new Event('pointerenter')); L('hover lines: '+document.querySelectorAll('#qboard > g:nth-child(2) line').length);
  $('play').click(); L('play: '+$('play').textContent);
 },500);
 setTimeout(()=>{ L('after 4s: change='+$('sRow').textContent+' time='+$('sTime').textContent+' call='+$('callbox').textContent);
   document.querySelector('[data-speed="10"]').click(); },4500);
 setTimeout(()=>{ L('x10 after 3s: change='+$('sRow').textContent);
   const r=$('strip').getBoundingClientRect();
   $('strip').dispatchEvent(new PointerEvent('pointerdown',{clientX:r.left+r.width*0.5,clientY:r.top+5}));
 },7500);
 setTimeout(()=>{ L('after seek to middle: change='+$('sRow').textContent+' lead='+$('sLead').textContent);
   document.querySelectorAll('.rope')[3].click(); L('following: '+document.querySelector('.rope.followed .num').textContent);
   document.querySelectorAll('#compGrid button')[359].click(); },9000);
 setTimeout(()=>{ L('after last-lead click: change='+$('sRow').textContent+' left='+$('sLeft').textContent+' call='+$('callbox').textContent);
   $('tMerge').click(); },12000);
 setTimeout(()=>{ L('merge after 24s: '+$('tCount').textContent+' | '+$('tMsg').textContent);
   document.body.setAttribute('data-log', JSON.stringify(__log)); }, 36000);
});
</script>"""
(SP / 'harness.html').write_text(s.replace('</body>', harness + '</body>'))
out = subprocess.run(['timeout', '90', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--headless=new', '--disable-gpu',
                      f'--user-data-dir={SP}/chrome', '--autoplay-policy=no-user-gesture-required', '--window-size=1280,2000',
                      '--virtual-time-budget=40000', '--dump-dom', f'file://{SP}/harness.html'], capture_output=True, text=True).stdout
subprocess.run(['pkill', '-f', f'{SP}/chrome'])
m = re.search(r'data-log="([^"]*)"', out)
for line in json.loads(html.unescape(m.group(1))) if m else ['NO LOG']:
    print(line)
