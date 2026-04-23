// Telegram Web Storage & Cookies Inspector
// Paste this script into DevTools console on https://web.telegram.org/* after the page loads
// It will print categorized localStorage keys, account structures, auth keys, salts, and cookies.
// Also copies a JSON export (if clipboard allowed) and exposes helper globals.

(function() {
  const START_TS = performance.now();
  const HEX_RE = /^[0-9a-f]+$/i;
  const BASE64_RE = /^[A-Za-z0-9+/]*={0,2}$/;

  function safeParse(json) {
    try { return JSON.parse(json); } catch { return null; }
  }

  function short(val, head=24, tail=24) {
    if (val == null) return String(val);
    if (typeof val !== 'string') val = String(val);
    if (val.length <= head + tail + 5) return val;
    return val.slice(0, head) + '...' + val.slice(-tail);
  }

  function isQuoted(str) {
    return typeof str === 'string' && str.startsWith('"') && str.endsWith('"');
  }

  function unwrapQuoted(str){
    return isQuoted(str) ? str.slice(1, -1) : str;
  }

  function classifyKey(k) {
    if (/^dc\d+_auth_key$/.test(k)) return 'authKey';
    if (/^dc\d+_server_salt$/.test(k)) return 'serverSalt';
    if (k === 'user_auth') return 'userAuth';
    if (k === 'dc') return 'dc';
    if (k === 'server_time_offset') return 'timeOffset';
    if (/^account\d+$/.test(k)) return 'account';
    if (k === 'tgme_sync') return 'tgmeSync';
    return 'other';
  }

  function analyseAuthKey(raw) {
    const val = unwrapQuoted(raw);
    const len = val.length;
    return {
      rawLength: raw.length,
      innerLength: len,
      quoted: isQuoted(raw),
      looksHex: HEX_RE.test(val),
      looksBase64: BASE64_RE.test(val) && !HEX_RE.test(val),
      fragment: short(val, 20, 20)
    };
  }

  function analyseServerSalt(raw) {
    const val = unwrapQuoted(raw);
    return {
      keyRaw: raw,
      unwrapped: val,
      length: val.length,
      looksHex: HEX_RE.test(val),
    };
  }

  function analyseAccount(key, raw) {
    const obj = safeParse(raw) || {};
    const authKeysInside = Object.entries(obj)
      .filter(([k,v]) => /_auth_key$/.test(k) && typeof v === 'string')
      .map(([k,v]) => ({ key: k, length: v.length, fragment: short(v) }));
    return {
      key,
      keys: Object.keys(obj),
      hasUserId: 'userId' in obj,
      dcId: obj.dcId,
      authKeys: authKeysInside,
      size: raw.length
    };
  }

  function collectCookies() {
    const cookieStr = document.cookie || '';
    if (!cookieStr) return [];
    return cookieStr.split(/; */).filter(Boolean).map(c => {
      const eq = c.indexOf('=');
      let name, value;
      if (eq === -1) { name = c; value = ''; } else {
        name = c.slice(0, eq);
        value = c.slice(eq + 1);
      }
      return {
        name,
        valueLength: value.length,
        sample: short(value, 15, 15)
      };
    });
  }

  // Scan localStorage
  const categories = {
    authKey: [],
    serverSalt: [],
    userAuth: [],
    dc: [],
    timeOffset: [],
    account: [],
    tgmeSync: [],
    other: []
  };

  const rawDump = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    const v = localStorage.getItem(k);
    rawDump[k] = v;
    const cls = classifyKey(k);
    categories[cls].push({ key: k, value: v });
  }

  // Detailed analyses
  const authKeysDetail = categories.authKey.map(item => ({
    key: item.key,
    ...analyseAuthKey(item.value)
  }));

  const serverSaltsDetail = categories.serverSalt.map(item => ({
    key: item.key,
    ...analyseServerSalt(item.value)
  }));

  const accountsDetail = categories.account.map(a => analyseAccount(a.key, a.value));

  let userAuthObj = null;
  if (categories.userAuth[0]) {
    userAuthObj = safeParse(categories.userAuth[0].value) || categories.userAuth[0].value;
  }

  const dcValue = categories.dc[0]?.value || null;
  const timeOffsetValue = categories.timeOffset[0]?.value || null;

  // Infer main DC
  let inferredDc = null;
  if (userAuthObj && typeof userAuthObj.dcID !== 'undefined') inferredDc = userAuthObj.dcID;
  else if (dcValue) inferredDc = dcValue;
  else if (authKeysDetail[0]) {
    const match = authKeysDetail[0].key.match(/^dc(\d+)_auth_key$/);
    if (match) inferredDc = match[1];
  }

  // Minimal session reconstruction
  const minimalSession = {};
  if (inferredDc) {
    const mainAuthKeyKey = `dc${inferredDc}_auth_key`;
    const mainAuthEntry = categories.authKey.find(e => e.key === mainAuthKeyKey);
    if (mainAuthEntry) minimalSession[mainAuthKeyKey] = mainAuthEntry.value;
  }
  if (categories.userAuth[0]) minimalSession['user_auth'] = categories.userAuth[0].value;
  if (dcValue) minimalSession['dc'] = dcValue;
  serverSaltsDetail.forEach(s => {
    if (s.key === `dc${inferredDc}_server_salt` || serverSaltsDetail.length === 1) {
      minimalSession[s.key] = rawDump[s.key];
    }
  });
  if (timeOffsetValue != null) minimalSession['server_time_offset'] = timeOffsetValue;

  // Cookies
  const cookies = collectCookies();

  const summary = {
    counts: {
      totalLocalStorageKeys: localStorage.length,
      authKeys: authKeysDetail.length,
      serverSalts: serverSaltsDetail.length,
      accounts: accountsDetail.length,
      cookies: cookies.length
    },
    inferredDc,
    hasUserAuth: !!userAuthObj,
    authKeys: authKeysDetail.map(a => ({
      key: a.key,
      length: a.innerLength,
      hex: a.looksHex,
      base64: a.looksBase64
    })),
    serverSalts: serverSaltsDetail.map(s => ({
      key: s.key,
      length: s.length,
      hex: s.looksHex
    })),
    accounts: accountsDetail.map(a => ({
      key: a.key,
      dcId: a.dcId,
      userId: a.hasUserId ? 'present' : 'missing',
      authKeysInside: a.authKeys.length
    }))
  };

  const exportPayload = {
    generatedAt: new Date().toISOString(),
    url: location.href,
    userAgent: navigator.userAgent,
    summary,
    minimalSession,
    userAuth: userAuthObj,
    fullLocalStorage: rawDump,
    cookies
  };

  // Console output
  const LINE = '─'.repeat(70);
  console.log('%c🔍 Telegram Web Storage Inspection', 'font-weight:bold;font-size:14px;');
  console.log(LINE);
  console.group('📦 Overview');
  console.log('Total localStorage keys:', localStorage.length);
  console.log('Auth keys:', authKeysDetail.length);
  console.log('Server salts:', serverSaltsDetail.length);
  console.log('Accounts:', accountsDetail.length);
  console.log('Cookies:', cookies.length);
  console.log('Inferred DC:', inferredDc);
  console.groupEnd();

  console.group('🔐 Auth Keys');
  authKeysDetail.forEach(a => {
    console.log(`${a.key}: length=${a.innerLength} hex=${a.looksHex} base64=${a.looksBase64} quoted=${a.quoted} sample=${a.fragment}`);
  });
  console.groupEnd();

  console.group('🧂 Server Salts');
  serverSaltsDetail.forEach(s => {
    console.log(`${s.key}: len=${s.length} hex=${s.looksHex} value=${short(s.unwrapped,16,16)}`);
  });
  console.groupEnd();

  console.group('👤 User Auth');
  console.log('user_auth raw:', categories.userAuth[0]?.value);
  console.log('parsed:', userAuthObj);
  console.log('dc key:', dcValue);
  console.log('server_time_offset:', timeOffsetValue);
  console.groupEnd();

  console.group('🗂 Accounts');
  accountsDetail.forEach(a => {
    console.group(a.key);
    console.log('dcId:', a.dcId);
    console.log('has userId:', a.hasUserId);
    console.log('auth keys inside:', a.authKeys.length);
    a.authKeys.forEach(k => console.log(`  ${k.key}: len=${k.length} sample=${k.fragment}`));
    console.groupEnd();
  });
  console.groupEnd();

  console.group('🍪 Cookies');
  cookies.forEach(c => {
    console.log(`${c.name}: length=${c.valueLength} sample=${c.sample}`);
  });
  console.groupEnd();

  console.group('🎯 Minimal Session (Reconstructable)');
  console.log(minimalSession);
  console.groupEnd();

  console.group('📤 Export Payload (object)');
  console.log(exportPayload);
  console.groupEnd();

  // Try to copy
  const jsonText = JSON.stringify(exportPayload, null, 2);
  (async () => {
    try {
      await navigator.clipboard.writeText(jsonText);
      console.log('✅ Export JSON copied to clipboard (size ~' + jsonText.length + ' chars)');
    } catch (e) {
      console.warn('⚠️ Could not copy to clipboard:', e);
    } finally {
      console.log('⏱ Done in', (performance.now() - START_TS).toFixed(1), 'ms');
    }
  })();

  // Expose helpers
  window.__tgStorageExport = exportPayload;
  window.__tgShowKey = (k) => console.log(k, localStorage.getItem(k));
  window.__tgRaw = rawDump;
  window.__tgMinimal = minimalSession;
  return exportPayload;
})();
