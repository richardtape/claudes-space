"""Replace AudioContext with a fake whose clock follows performance.now(), record every strike,
and check the ringing schedule: rounds first, one bell per blow, handstroke gap, peal speed."""
import sys, subprocess, json, html, re, pathlib
SP = pathlib.Path(sys.argv[1]); HERE = pathlib.Path(__file__).parent.parent
s = (HERE / 'index.html').read_text()
fake = r"""<script>
window.__strikes=[];
class FakeNode{constructor(){this.gain={value:1,linearRampToValueAtTime(){}};this.pan={value:0};this.threshold={value:0};this.ratio={value:0}}connect(){}start(w){__strikes.push([this.__bell,w])}stop(){}}
class FakeCtx{constructor(){this.sampleRate=8000;this.destination=new FakeNode();this.t0=performance.now()}
 get currentTime(){return (performance.now()-this.t0)/1000}resume(){}
 createGain(){return new FakeNode()}createDynamicsCompressor(){return new FakeNode()}createConvolver(){return new FakeNode()}createStereoPanner(){return new FakeNode()}
 createBuffer(c,n){const d=[...Array(c)].map(()=>new Float32Array(n));return{getChannelData:i=>d[i],__n:n}}
 createBufferSource(){const n=new FakeNode();Object.defineProperty(n,'buffer',{set(b){n.__bell=b.__bell}});return n}}
window.AudioContext=FakeCtx;
</script>"""
s = s.replace('<head>', '<head>' + fake, 1)
# tag buffers with their bell number so strikes can be identified
s = s.replace("buffers[b] = render(ctx, b, 5.5 + 0.5 * (b - 1) / 7);", "buffers[b] = render(ctx, b, 5.5 + 0.5 * (b - 1) / 7); buffers[b].__bell = b;")
assert "buffers[b].__bell = b" in s
probe = r"""<script>window.addEventListener('load',()=>{
 setTimeout(()=>document.getElementById('play').click(),300);
 setTimeout(()=>{document.body.setAttribute('data-out',JSON.stringify({strikes:__strikes.slice(0,80),n:__strikes.length,row:document.getElementById('sRow').textContent,time:document.getElementById('sTime').textContent}))},12300);
});</script>"""
(SP / 'audio.html').write_text(s.replace('</body>', probe + '</body>'))
out = subprocess.run(['timeout', '60', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--headless=new', '--disable-gpu',
                      f'--user-data-dir={SP}/chrome', '--window-size=1280,1200', '--virtual-time-budget=14000', '--dump-dom',
                      f'file://{SP}/audio.html'], capture_output=True, text=True).stdout
subprocess.run(['pkill', '-f', f'{SP}/chrome'])
d = json.loads(html.unescape(re.search(r'data-out="([^"]*)"', out).group(1)))
st = d['strikes']
bells = [b for b, w in st]
print('strikes scheduled in ~12 s:', d['n'], ' display: change', d['row'], 'time', d['time'])
print('first 4 rows (rounds):', [bells[i * 8:i * 8 + 8] for i in range(4)])
print('rows 5-8:', [''.join(map(str, bells[i * 8:i * 8 + 8])) for i in range(4, 8)])
gaps = [round(st[i + 1][1] - st[i][1], 4) for i in range(31)]
print('gaps between blows (s):', sorted(set(gaps)))
assert all(sorted(bells[i * 8:i * 8 + 8]) == list(range(1, 9)) for i in range(len(bells) // 8)), 'each row has each bell once'
print('each row contains each bell once: ok')
