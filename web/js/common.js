/* Duet — shared utilities (theme, gamification, speech, helpers) */

/* ── Admin services config (all free tier, all optional) ──
   GA4:        https://analytics.google.com → Data Stream → Measurement ID (G-XXXXXXXXXX)
   Clarity:    https://clarity.microsoft.com → New Project → Project ID (10-char string)
   Formspree:  https://formspree.io → New Form → endpoint URL (https://formspree.io/f/xxxxxxxx)
   If Formspree is null, subscriber emails get stashed in localStorage and you can
   export them from the admin section in /analytics.html.
*/
(function () {
  const GA4_ID = null;       // e.g. 'G-XXXXXXXXXX'
  const CLARITY_ID = null;   // e.g. 'abcd1234ef'
  if (GA4_ID) {
    const s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA4_ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag('js', new Date());
    gtag('config', GA4_ID, { anonymize_ip: true });
  }
  if (CLARITY_ID) {
    (function (c, l, a, r, i, t, y) {
      c[a] = c[a] || function () { (c[a].q = c[a].q || []).push(arguments); };
      t = l.createElement(r); t.async = 1; t.src = 'https://www.clarity.ms/tag/' + i;
      y = l.getElementsByTagName(r)[0]; y.parentNode.insertBefore(t, y);
    })(window, document, 'clarity', 'script', CLARITY_ID);
  }
})();

(function (global) {
  'use strict';

  // ── HTML escape ──
  const ESC = { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' };
  function escape(s) { return String(s).replace(/[&<>"']/g, c => ESC[c]); }
  function escapeReg(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  // ── Theme (persistent + optional auto-by-time) ──
  function applyTheme() {
    const stored = localStorage.getItem('duet-theme');
    const mode = localStorage.getItem('duet-theme-mode') || 'manual'; // manual | auto
    let t;
    if (mode === 'auto') {
      const h = new Date().getHours();
      t = (h >= 6 && h < 18) ? 'light' : 'dark';
    } else {
      t = stored || 'dark';
    }
    document.documentElement.dataset.theme = t;
    return t;
  }
  function bindThemeToggle(btnId) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.textContent = applyTheme() === 'dark' ? '🌙' : '☀️';
    btn.addEventListener('click', () => {
      const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      btn.textContent = next === 'dark' ? '🌙' : '☀️';
      localStorage.setItem('duet-theme', next);
    });
  }

  // ── Gamification ──
  const BADGES = [
    { id:'first',     emoji:'🌱', name:'First Step',  hint:'完成第一篇文章測驗' },
    { id:'bookworm',  emoji:'📚', name:'Bookworm',    hint:'完成 3 篇文章' },
    { id:'scholar',   emoji:'🎓', name:'Scholar',     hint:'完成全部 5 篇文章' },
    { id:'streaker',  emoji:'🔥', name:'On Fire',     hint:'連續 3 天造訪' },
    { id:'polyglot',  emoji:'🌐', name:'Polyglot',    hint:'試過全部三種語言模式' },
    { id:'pronouncer',emoji:'🔊', name:'Pronouncer',  hint:'使用發音功能 5 次' },
    { id:'reviewer',  emoji:'🃏', name:'Reviewer',    hint:'完成 10 個單字複習' },
  ];
  const DEFAULT_STATS = {
    xp:0, level:1, streak:0, lastVisit:null, read:[],
    badges:[], modesTried:[], speakCount:0, vocabReviews:0
  };
  function getStats() {
    try { return Object.assign({}, DEFAULT_STATS, JSON.parse(localStorage.getItem('duet-stats') || '{}')); }
    catch { return Object.assign({}, DEFAULT_STATS); }
  }
  function saveStats(s) { localStorage.setItem('duet-stats', JSON.stringify(s)); }
  function xpToLevel(xp) { return Math.floor(Math.sqrt(xp / 50)) + 1; }
  function nextLevelXP(lv) { return lv * lv * 50; }

  function bumpStreak() {
    const s = getStats();
    const today = new Date().toISOString().slice(0, 10);
    if (s.lastVisit === today) return s;
    if (!s.lastVisit) s.streak = 1;
    else {
      const diff = Math.round((new Date(today) - new Date(s.lastVisit)) / 86400000);
      s.streak = (diff === 1) ? s.streak + 1 : 1;
    }
    s.lastVisit = today;
    saveStats(s);
    if (s.streak >= 3) addBadge('streaker');
    return s;
  }

  function addBadge(id) {
    const s = getStats();
    if (s.badges.includes(id)) return;
    s.badges.push(id); saveStats(s);
    showBadgeUnlock(id);
  }
  function showBadgeUnlock(id) {
    const b = BADGES.find(x => x.id === id);
    if (!b) return;
    const el = document.createElement('div');
    el.className = 'badge-unlock';
    el.innerHTML = `<div class="bu-card"><div class="bu-emoji">${b.emoji}</div><div class="bu-label">徽章解鎖！</div><div class="bu-name">${b.name}</div></div>`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2400);
  }
  function awardXP(n) {
    const s = getStats();
    s.xp += n; saveStats(s);
    showToast(`+${n} XP`);
  }
  function showToast(text, type) {
    const t = document.createElement('div');
    t.className = 'xp-toast' + (type ? ' ' + type : '');
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 1800);
  }

  // ── Mark article as read (when quiz finished) ──
  function markRead(id) {
    if (!id) return;
    const read = new Set(JSON.parse(localStorage.getItem('duet-read') || '[]'));
    if (read.has(id)) return false;
    read.add(id);
    localStorage.setItem('duet-read', JSON.stringify([...read]));
    const s = getStats(); s.read = [...read]; saveStats(s);
    if (read.size >= 1) addBadge('first');
    if (read.size >= 3) addBadge('bookworm');
    if (read.size >= 5) addBadge('scholar');
    return true;
  }

  // ── Web Speech API (with voice preload + audio ducking) ──
  let _voicesCache = null;
  function _loadVoices() {
    return new Promise(resolve => {
      if (!window.speechSynthesis) return resolve([]);
      const v = window.speechSynthesis.getVoices();
      if (v.length) { _voicesCache = v; return resolve(v); }
      window.speechSynthesis.addEventListener('voiceschanged', () => {
        _voicesCache = window.speechSynthesis.getVoices();
        resolve(_voicesCache);
      }, { once:true });
      setTimeout(() => resolve(window.speechSynthesis.getVoices() || []), 500);
    });
  }
  if (window.speechSynthesis) _loadVoices();

  async function speak(text, lang, btn) {
    if (!text || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const voices = _voicesCache || await _loadVoices();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang || (/[\u4e00-\u9fff]/.test(text) ? 'zh-TW' : 'en-US');
    u.rate = 0.92; u.pitch = 1.0; u.volume = 1.0;
    const m = voices.find(v => v.lang.startsWith(u.lang.split('-')[0]) && /Google|Apple|Microsoft|Samantha|Karen|Daniel|Mei/i.test(v.name));
    if (m) u.voice = m;
    // Audio ducking
    const bg = global._bgMusic, origVol = bg ? bg.volume : null;
    if (bg && !bg.paused) bg.volume = origVol * 0.25;
    const restore = () => {
      if (bg && origVol != null) bg.volume = origVol;
      if (btn) btn.classList.remove('speaking');
    };
    u.onend = u.onerror = restore;
    if (btn) btn.classList.add('speaking');
    window.speechSynthesis.speak(u);
    // Stat tracking
    const s = getStats();
    s.speakCount = (s.speakCount || 0) + 1; saveStats(s);
    if (s.speakCount >= 5) addBadge('pronouncer');
  }

  // ── Background music (curated calm tracks — real human performances) ──
  const TRACKS = [
    // Modern neoclassical / contemporary piano (warm, expressive)
    { title:'Lago di Como · Novarina',           src:'audio/piano_lago.mp3' },
    { title:'Brand New Days · Novarina',         src:'audio/piano_newdays.mp3' },
    { title:'Natural · MaaBo',                   src:'audio/piano_natural.mp3' },
    { title:'Snow Slow · Vallarino',             src:'audio/piano_butterfly.mp3' },
    { title:'Old Russian Waltz · Lena Orsa',     src:'audio/piano_waltz.mp3' },
    { title:'Meditative Magic · Alexis',         src:'audio/ambient_magic.mp3' },
    // Classical (kept as variety)
    { title:'Clair de Lune · Debussy',           src:'audio/debussy.mp3' },
    { title:'Nocturne Op.9 No.2 · Chopin',       src:'audio/chopin.mp3' },
  ];
  function initMusic(btnId) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    let curIdx = Math.floor(Math.random() * TRACKS.length);
    const a = new Audio(TRACKS[curIdx].src);
    a.volume = 0.28; a.loop = true;
    global._bgMusic = a;
    btn.title = `${TRACKS[curIdx].title} (雙擊換首)`;
    let playing = false;
    const setPlaying = v => {
      playing = v;
      btn.classList.toggle('playing', v);
      btn.textContent = v ? '🎵' : '🔇';
    };
    btn.addEventListener('click', () => {
      playing ? (a.pause(), setPlaying(false)) : a.play().then(() => setPlaying(true)).catch(()=>{});
    });
    btn.addEventListener('dblclick', () => {
      curIdx = (curIdx + 1) % TRACKS.length;
      a.src = TRACKS[curIdx].src;
      btn.title = `${TRACKS[curIdx].title} (雙擊換首)`;
      showToast(`🎵 ${TRACKS[curIdx].title}`);
      a.play().then(() => setPlaying(true)).catch(()=>{});
    });
    // Default OFF — user clicks to start
    btn.textContent = '🔇';
  }

  // ── Welcome chime (Web Audio with autoplay fallback) ──
  let _chimeFired = false;
  function playWelcomeChime(delay) {
    setTimeout(() => {
      if (_chimeFired) return;
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const fire = () => {
          if (_chimeFired) return; _chimeFired = true;
          [[523.25, 0], [659.25, 0.18], [783.99, 0.36]].forEach(([f, t]) => {
            const o = ctx.createOscillator(), g = ctx.createGain();
            o.connect(g); g.connect(ctx.destination);
            o.type = 'sine'; o.frequency.value = f;
            g.gain.setValueAtTime(0, ctx.currentTime + t);
            g.gain.linearRampToValueAtTime(0.12, ctx.currentTime + t + 0.05);
            g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + t + 1.0);
            o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 1.0);
          });
        };
        if (ctx.state === 'suspended') {
          const unlock = () => {
            ctx.resume().then(fire);
            ['pointerdown','keydown','touchstart'].forEach(e => document.removeEventListener(e, unlock));
          };
          ['pointerdown','keydown','touchstart'].forEach(e => document.addEventListener(e, unlock, { once:true }));
        } else fire();
      } catch (e) {}
    }, delay || 0);
  }

  // ── Public API ──
  global.Duet = {
    escape, escapeReg,
    applyTheme, bindThemeToggle,
    BADGES, getStats, saveStats, xpToLevel, nextLevelXP,
    bumpStreak, addBadge, awardXP, showToast, markRead,
    speak, initMusic, playWelcomeChime,
    FORMSPREE_ENDPOINT: null,  // set to 'https://formspree.io/f/xxxxxxxx' to enable email subscribe
  };
})(window);
