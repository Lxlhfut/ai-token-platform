const API = '';

function getToken() { return localStorage.getItem('token'); }
function setToken(t) { localStorage.setItem('token', t); }
function clearToken() { localStorage.removeItem('token'); }

<<<<<<< HEAD
// ======= 浮空客服 =======
function toggleCsPopup() {
  document.getElementById('csPopup').classList.toggle('open');
}
function copyQQ() {
  navigator.clipboard.writeText('2195127736').then(() => {
    var h = document.getElementById('csCopyHint');
    h.textContent = '已复制';
    setTimeout(function(){ h.textContent = '复制'; }, 2000);
  });
}
// 点击弹窗外关闭
document.addEventListener('click', function(e) {
  var popup = document.getElementById('csPopup');
  var btn = document.getElementById('csFloat');
  if (popup && btn && popup.classList.contains('open') && !popup.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
    popup.classList.remove('open');
  }
});

=======
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
// ======= 侧边栏标签页切换 =======
function switchTab(tab, el) {
  // 激活侧边栏项
  document.querySelectorAll('.sidebar-item').forEach(item => item.classList.remove('active'));
  if (el) el.classList.add('active');
  // 显示对应标签页
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  const pane = document.getElementById('pane-' + tab);
  if (pane) pane.classList.add('active');
  // 移动端自动关闭侧边栏
  closeSidebar();
}

// ======= 移动端侧边栏切换 =======
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sidebar && overlay) {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  }
}
function closeSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
}

function formatError(data) {
  if (!data || !data.detail) return '请求失败';
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map(e => e.msg || JSON.stringify(e)).join('; ');
  }
  return String(data.detail);
}

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(API + path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(formatError(data) || (data.error && data.error.message) || '请求失败');
  return data;
}

function fmtTime(s) { return s ? new Date(s).toLocaleString('zh-CN') : '-'; }
function fmtMoney(n) { return '\u00a5' + Number(n).toFixed(4); }

// ============================================================
//  消息通知系统（用户端和管理端共用）
//  浮动铃铛 + 浮动面板，均支持拖拽
// ============================================================
let _notifyPollTimer = null;
let _notifyDrag = { active: false, startX: 0, startY: 0, elX: 0, elY: 0, target: null };

// ======= 铃铛显隐（登录后显示，登录前/首页隐藏） =======

function showFloatingBell() {
  const bell = document.getElementById('floating-bell');
  if (bell) bell.style.display = 'block';
}

function hideFloatingBell() {
  const bell = document.getElementById('floating-bell');
  if (bell) bell.style.display = 'none';
  closeNotifyFloat();
}

function startNotifyPoll() {
  stopNotifyPoll();
  _notifyPollTimer = setInterval(loadNotifyUnreadCount, 20000); // 每20秒
  loadNotifyUnreadCount();
}

function stopNotifyPoll() {
  if (_notifyPollTimer) { clearInterval(_notifyPollTimer); _notifyPollTimer = null; }
}

async function loadNotifyUnreadCount() {
  try {
    const data = await api('/api/notifications/unread-count');
    const badge = document.getElementById('notify-badge');
    if (badge) {
      badge.textContent = data.count > 99 ? '99+' : data.count;
      badge.style.display = data.count > 0 ? 'flex' : 'none';
    }
  } catch (e) { /* 静默失败 */ }
}

async function loadNotifications() {
  const list = document.getElementById('notify-list');
  if (!list) return;
  try {
    const records = await api('/api/notifications/list');
    if (!records.length) {
      list.innerHTML = '<div class="notify-empty">暂无消息</div>';
      return;
    }
    list.innerHTML = records.map(r =>
      '<div class="notify-item' + (r.is_read ? '' : ' unread') +
        '" onclick="markNotificationRead(' + r.id + ', event, \'' +
        escapeAttr(r.nav_tab || '') + '\', \'' +
        escapeAttr(r.nav_section || '') + '\')" title="' +
        (r.nav_tab ? '点击跳转到对应页面' : '') + '">' +
        '<span class="n-title">' + r.type_label + '</span>' +
        '<span class="n-msg">' + (r.message || '') + '</span>' +
        '<span class="n-time">' + fmtTime(r.created_at) + '</span>' +
      '</div>'
    ).join('');
  } catch (e) {
    list.innerHTML = '<div class="notify-empty">加载失败</div>';
  }
}

async function markNotificationRead(id, event, navTab, navSection) {
  if (event) event.stopPropagation();
  try {
    await api('/api/notifications/' + id + '/read', { method: 'POST' });
    await loadNotifyUnreadCount();
    await loadNotifications();
  } catch (e) { /* 静默 */ }
  // 如果关联了导航目标，关闭消息面板并跳转
  if (navTab) {
    closeNotifyFloat();
    navigateToTab(navTab);
    if (navSection) {
      setTimeout(() => scrollToSection(navSection), 200);
    }
  }
}

async function markAllNotificationsRead(event) {
  if (event) event.stopPropagation();
  try {
    await api('/api/notifications/read-all', { method: 'POST' });
    await loadNotifyUnreadCount();
    await loadNotifications();
  } catch (e) { /* 静默 */ }
}

// ======= 浮动面板开关 =======

function toggleNotifyFloat(event) {
  if (event) event.stopPropagation();
  const panel = document.getElementById('notify-float');
  if (!panel) return;
  const isOpen = panel.classList.contains('open');
  if (isOpen) {
    closeNotifyFloat();
  } else {
    panel.classList.add('open');
    loadNotifications();
  }
}

function closeNotifyFloat(event) {
  if (event) event.stopPropagation();
  const panel = document.getElementById('notify-float');
  if (panel) panel.classList.remove('open');
}

// ======= 通知消息点击后跳转到对应页面 =======

function navigateToTab(tab) {
  // 激活侧边栏对应项 + 显示对应标签页
  const sidebarItem = document.querySelector('.sidebar-item[data-tab="' + tab + '"]');
  switchTab(tab, sidebarItem);
}

function scrollToSection(sectionId) {
  const el = document.getElementById(sectionId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// 点击空白处关闭浮窗
document.addEventListener('click', function(e) {
  const panel = document.getElementById('notify-float');
  const bell = document.getElementById('floating-bell');
  if (panel && panel.classList.contains('open') &&
      !bell.contains(e.target) && !panel.contains(e.target)) {
    panel.classList.remove('open');
  }
});

// ======= 拖拽功能（铃铛 + 面板共用状态机） =======

document.addEventListener('mousedown', function(e) {
  const bell = document.getElementById('floating-bell');
  const panel = document.getElementById('notify-float');
  const header = document.getElementById('notify-float-header');

  // 铃铛拖拽
  if (bell && bell.contains(e.target) && e.target.tagName !== 'BUTTON' && !e.target.closest('button')) {
    _notifyDrag.active = true;
    _notifyDrag.target = 'bell';
    _notifyDrag.startX = e.clientX;
    _notifyDrag.startY = e.clientY;
    const rect = bell.getBoundingClientRect();
    _notifyDrag.elX = rect.left;
    _notifyDrag.elY = rect.top;
    e.preventDefault();
    return;
  }

  // 面板标题栏拖拽
  if (header && panel && header.contains(e.target)) {
    if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
    _notifyDrag.active = true;
    _notifyDrag.target = 'panel';
    _notifyDrag.startX = e.clientX;
    _notifyDrag.startY = e.clientY;
    const rect = panel.getBoundingClientRect();
    _notifyDrag.elX = rect.left;
    _notifyDrag.elY = rect.top;
    e.preventDefault();
  }
});

document.addEventListener('mousemove', function(e) {
  if (!_notifyDrag.active) return;

  const dx = e.clientX - _notifyDrag.startX;
  const dy = e.clientY - _notifyDrag.startY;

  let newX = _notifyDrag.elX + dx;
  let newY = _notifyDrag.elY + dy;

  if (_notifyDrag.target === 'bell') {
    const bell = document.getElementById('floating-bell');
    if (!bell) return;
    const maxX = window.innerWidth - bell.offsetWidth - 8;
    const maxY = window.innerHeight - bell.offsetHeight - 8;
    newX = Math.max(0, Math.min(newX, maxX));
    newY = Math.max(0, Math.min(newY, maxY));
    bell.style.left = newX + 'px';
    bell.style.top = newY + 'px';
    bell.style.right = 'auto';
  } else if (_notifyDrag.target === 'panel') {
    const panel = document.getElementById('notify-float');
    if (!panel) return;
    const maxX = window.innerWidth - panel.offsetWidth - 8;
    const maxY = window.innerHeight - 60;
    newX = Math.max(0, Math.min(newX, maxX));
    newY = Math.max(0, Math.min(newY, maxY));
    panel.style.left = newX + 'px';
    panel.style.top = newY + 'px';
    panel.style.right = 'auto';
  }
});

document.addEventListener('mouseup', function() {
  _notifyDrag.active = false;
  _notifyDrag.target = null;
});

async function initUserDashboard() {
  // ======= Tab 切换（登录 / 注册） =======
  document.querySelectorAll('#auth-panel .tab').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('#auth-panel .tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const isLogin = btn.dataset.tab === 'login';
      document.getElementById('login-form').style.display = isLogin ? 'block' : 'none';
      document.getElementById('register-form').style.display = isLogin ? 'none' : 'block';
      document.getElementById('auth-msg').textContent = '';
    };
  });

  // ======= 登录 =======
  document.getElementById('login-form').onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = document.getElementById('auth-msg');
    msg.textContent = '';
    try {
      const r = await api('/api/user/login', {
        method: 'POST',
        body: JSON.stringify({ username: fd.get('username'), password: fd.get('password') }),
      });
      setToken(r.access_token);
      await loadUserPanel();
    } catch (err) {
      msg.textContent = err.message;
    }
  };

  // ======= 注册 =======
  document.getElementById('register-form').onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = document.getElementById('auth-msg');
    msg.textContent = '';
    if (!fd.get('agreed_terms')) {
      msg.textContent = '请先阅读并同意用户注册协议和隐私政策';
      return;
    }
    const password = fd.get('password');
    const confirmPassword = fd.get('confirm_password');
    if (password !== confirmPassword) {
      msg.textContent = '两次输入的密码不一致';
      return;
    }
    const inviteCode = (fd.get('invite_code') || '').trim();
    try {
      await api('/api/user/register', {
        method: 'POST',
        body: JSON.stringify({
          username: fd.get('username'),
          password: password,
          agreed_terms: true,
          invite_code: inviteCode || null,
        }),
      });
      const r = await api('/api/user/login', {
        method: 'POST',
        body: JSON.stringify({ username: fd.get('username'), password: password }),
      });
      setToken(r.access_token);
      await loadUserPanel();
    } catch (err) {
      msg.textContent = err.message;
    }
  };

  // 检查 URL 参数 ?ref=邀请码，自动填入注册表单
  const urlRef = new URLSearchParams(window.location.search).get('ref');
  if (urlRef) {
    const inviteInput = document.querySelector('#register-form [name="invite_code"]');
    if (inviteInput) inviteInput.value = urlRef;
    // 自动切换到注册 Tab
    const regTab = document.querySelector('#auth-panel .tab[data-tab="register"]');
    if (regTab) regTab.click();
  }

  document.getElementById('logout-btn').onclick = () => { stopNotifyPoll(); clearToken(); location.reload(); };
<<<<<<< HEAD
  document.getElementById('create-key-btn').onclick = () => showApiKeyForm(null);
=======
  document.getElementById('create-key-btn').onclick = async () => {
    try {
      await api('/api/user/api-keys', { method: 'POST', body: JSON.stringify({ name: 'key-' + Date.now() }) });
      await loadUserPanel();
    } catch (err) { alert(err.message); }
  };
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03

  // 兑换码充值
  document.getElementById('redeem-btn').onclick = async () => {
    const code = document.getElementById('redeem-input').value.trim();
    const msg = document.getElementById('redeem-msg');
    msg.textContent = '';
    msg.style.color = 'var(--danger)';
    if (!code) { msg.textContent = '请输入兑换码'; return; }
    try {
      const result = await api('/api/user/redeem', { method: 'POST', body: JSON.stringify({ code }) });
      msg.style.color = 'var(--success)';
      msg.textContent = '兑换成功！充值 ' + fmtMoney(result.amount) + '，当前余额：' + fmtMoney(result.balance);
      document.getElementById('redeem-input').value = '';
      await loadUserPanel();
    } catch (err) {
      msg.textContent = err.message;
    }
  };

<<<<<<< HEAD
  window._wechatOrderNo = null;
  window._wechatPollTimer = null;
=======
  // 扫码支付：选择支付方式
  window._selectedPayMethod = 'wechat';
  window._selectedScanAmount = null;
  window._currentOrderNo = null;
  window._platformQrcodes = {};  // {"wechat_10": "/static/...", ...}

  // 预加载平台收款码
  try {
    const qrcodes = await fetch('/api/platform-qrcodes').then(r => r.json());
    qrcodes.forEach(q => {
      window._platformQrcodes[q.pay_method + '_' + q.amount] = q.qrcode_path;
    });
  } catch (e) { /* 静默 */ }

  // 生成支付二维码
  document.getElementById('create-order-btn').onclick = async () => {
    const amount = window._selectedScanAmount;
    const msg = document.getElementById('redeem-msg');
    msg.textContent = '';
    msg.style.color = 'var(--danger)';
    if (!amount) { msg.textContent = '请先选择充值金额'; return; }
    try {
      const order = await api('/api/user/recharge-order', {
        method: 'POST',
        body: JSON.stringify({ amount, pay_method: window._selectedPayMethod }),
      });
      window._currentOrderNo = order.order_no;
      const methodLabel = window._selectedPayMethod === 'wechat' ? '微信' : '支付宝';
      document.getElementById('payment-info').textContent = '请使用 ' + methodLabel + ' 扫描下方收款码支付';
      document.getElementById('qr-amount-display').textContent = '¥' + amount.toFixed(2);
      document.getElementById('qr-order-no').textContent = '订单号：' + order.order_no;

      // 显示对应金额的收款码
      const qrKey = window._selectedPayMethod + '_' + amount;
      const qrPath = window._platformQrcodes[qrKey];
      const imgEl = document.getElementById('qr-code-image');
      const noImgEl = document.getElementById('qr-no-image');
      if (qrPath && imgEl) {
        imgEl.src = qrPath;
        imgEl.style.display = 'block';
        if (noImgEl) noImgEl.style.display = 'none';
      } else {
        if (imgEl) imgEl.style.display = 'none';
        if (noImgEl) {
          noImgEl.style.display = 'block';
          noImgEl.innerHTML = '<span style="font-size:3rem">📱</span><p style="margin-top:8px;color:#f59e0b">该面额收款码尚未上传</p>';
        }
      }

      document.getElementById('payment-modal').style.display = 'flex';
    } catch (err) {
      msg.textContent = err.message;
    }
  };
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03

  if (getToken()) loadUserPanel();
}

async function loadUserPanel() {
  try {
    const [user, config, pricing] = await Promise.all([
      api('/api/user/me'),
      fetch('/api/config').then(r => r.json()),
      fetch('/api/user/pricing').then(r => r.json()),
    ]);

    document.getElementById('auth-panel').style.display = 'none';
    document.getElementById('app-layout').style.display = 'flex';
    document.getElementById('logout-btn').style.display = 'inline-flex';
    showFloatingBell();
    startNotifyPoll();
    document.getElementById('balance').textContent = fmtMoney(user.balance);
    document.getElementById('username').textContent = user.username;
    document.getElementById('email').textContent = user.email || user.username;

    const balanceHint = document.getElementById('balance-hint');
    const balanceCard = document.querySelector('.stat-balance');
    if (user.balance <= 0) {
      balanceHint.textContent = '\u4f59\u989d\u4e3a 0\uff0c\u8bf7\u5148\u5145\u503c\u540e\u518d\u8c03\u7528';
      balanceCard.classList.add('stat-warning');
    } else {
      balanceHint.textContent = '\u53ef\u7528\u4e8e\u6309\u91cf\u6263\u8d39';
      balanceCard.classList.remove('stat-warning');
    }

    document.getElementById('recharge-notice').textContent = config.recharge_notice || '';

    const keys = await api('/api/user/api-keys');
<<<<<<< HEAD
    window._apiKeysData = {};
    keys.forEach(k => { window._apiKeysData[k.id] = k; });
=======
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
    const firstKey = keys.length ? keys[0].key : '（请先创建 API Key）';
    const baseUrl = window.location.origin + '/v1';

    // 接入配置卡片（概览 + API Key 两个标签页）
    const baseUrlEls = ['display-base-url', 'display-base-url-2'];
    const apiKeyEls = ['display-api-key', 'display-api-key-2'];
    baseUrlEls.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = baseUrl; });
    apiKeyEls.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = firstKey; });

    document.getElementById('keys-list').innerHTML = keys.length
<<<<<<< HEAD
      ? keys.map(k => {
          const allowedStr = (k.allowed_models && k.allowed_models.length)
            ? '<br><span style="color:var(--muted);font-size:.78rem">限调: ' + k.allowed_models.slice(0, 5).join(', ') + (k.allowed_models.length > 5 ? '...' : '') + '</span>'
            : '<br><span style="color:var(--muted);font-size:.78rem">不限模型</span>';
          return '<div class="key-item"><div><span class="key-name">' + k.name + '</span><code class="key-value">' + k.key + '</code>' + allowedStr + '</div>' +
            '<div style="display:flex;gap:6px">' +
            '<button class="btn btn-outline btn-sm" data-key="' + k.key + '" onclick="copyText(this.dataset.key, this)">复制</button>' +
            '<button class="btn btn-outline btn-sm" onclick="showApiKeyForm(' + k.id + ', window._apiKeysData[' + k.id + '])">编辑</button>' +
            '<button class="btn btn-outline btn-sm" style="color:var(--danger)" onclick="deleteApiKey(' + k.id + ')">删除</button>' +
            '</div></div>';
        }).join('')
=======
      ? keys.map(k => '<div class="key-item"><div><span class="key-name">' + k.name + '</span><code class="key-value">' + k.key + '</code></div><button class="btn btn-outline btn-sm" data-key="' + k.key + '" onclick="copyText(this.dataset.key, this)">复制</button></div>').join('')
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
      : '<p class="muted-text">暂无 Key，请点击创建新 Key</p>';

    // Python 代码示例
    const codeEl = document.getElementById('code-example');
    if (codeEl) {
      updateCodeExample(firstKey, baseUrl);
    }

<<<<<<< HEAD
    window._pricingData = pricing;
    window._pricingView = 'table';
    buildPricingSeriesChips(pricing);
    filterPricing();
=======
    document.getElementById('pricing-body').innerHTML = pricing.length
      ? pricing.map(p => '<tr><td><code>' + p.model + '</code></td><td>' + p.input_price + '</td><td>' + p.output_price + '</td><td>' + (p.description || '-') + '</td></tr>').join('')
      : '<tr><td colspan="4">暂无定价信息</td></tr>';
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03

    const usage = await api('/api/user/usage');
    document.getElementById('usage-body').innerHTML = usage.length
      ? usage.map(u => '<tr><td>' + fmtTime(u.created_at) + '</td><td>' + u.model + '</td><td>' + u.total_tokens + '</td><td>' + fmtMoney(u.cost) + '</td><td>' + u.status + '</td></tr>').join('')
      : '<tr><td colspan="5">\u6682\u65e0\u8c03\u7528\u8bb0\u5f55\uff0c\u5145\u503c\u540e\u53ef\u5f00\u59cb\u4f7f\u7528</td></tr>';

    const txs = await api('/api/user/transactions');
    const typeLabel = { recharge: '充值', consume: '消费', refund: '退款', adjust: '调整' };
    document.getElementById('tx-body').innerHTML = txs.length
      ? txs.map(t => '<tr><td>' + fmtTime(t.created_at) + '</td><td>' + (typeLabel[t.type] || t.type) + '</td><td>' + fmtMoney(t.amount) + '</td><td>' + fmtMoney(t.balance_after) + '</td><td>' + (t.remark || '') + '</td></tr>').join('')
      : '<tr><td colspan="5">暂无交易记录，充值后显示在此</td></tr>';

    // 加载充值订单列表
    try {
      const orders = await api('/api/user/recharge-orders');
      const statusLabel = { pending: '待支付', submitted: '待审核', paid: '已到账', cancelled: '已取消' };
<<<<<<< HEAD
      const payLabel = { wechat: '微信扫码', alipay: '支付宝', wechat_pay: '微信支付' };
=======
      const payLabel = { wechat: '微信', alipay: '支付宝' };
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
      document.getElementById('recharge-orders-body').innerHTML = orders.length
        ? orders.map(o =>
            '<tr>' +
            '<td>' + fmtTime(o.created_at) + '</td>' +
            '<td>' + fmtMoney(o.amount) + '</td>' +
            '<td>' + (payLabel[o.pay_method] || o.pay_method) + '</td>' +
            '<td>' + (statusLabel[o.status] || o.status) + '</td>' +
            '</tr>'
          ).join('')
        : '<tr><td colspan="4" style="color:var(--muted)">暂无充值记录</td></tr>';
    } catch (e) {
      document.getElementById('recharge-orders-body').innerHTML = '<tr><td colspan="4" style="color:var(--muted)">加载失败</td></tr>';
    }

    // 加载代理信息（静默，不阻塞主流程）
    loadAgentInfo().catch(() => {});
  } catch {
    clearToken();
  }
}

function initAdminDashboard() {
  document.getElementById('admin-login-form').onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const msg = document.getElementById('admin-auth-msg');
    msg.textContent = '';
    try {
      const r = await api('/api/user/login', {
        method: 'POST',
        body: JSON.stringify({ username: fd.get('username'), password: fd.get('password') }),
      });
      setToken(r.access_token);
      await loadAdminPanel();
    } catch (err) {
      msg.textContent = err.message;
    }
  };
  document.getElementById('admin-logout').onclick = () => { stopNotifyPoll(); clearToken(); location.reload(); };
  if (getToken()) loadAdminPanel().catch(() => clearToken());
}

async function loadAdminPanel() {
  const stats = await api('/api/admin/stats');
  document.getElementById('admin-login').style.display = 'none';
  document.getElementById('app-layout').style.display = 'flex';
  document.getElementById('admin-logout').style.display = 'inline-flex';
  showFloatingBell();
  startNotifyPoll();
  document.getElementById('admin-stats').innerHTML =
    '<div class="card stat"><span class="stat-label">\u603b\u7528\u6237</span><span class="stat-value">' + stats.total_users + '</span></div>' +
    '<div class="card stat"><span class="stat-label">\u7528\u6237\u603b\u4f59\u989d</span><span class="stat-value">' + fmtMoney(stats.total_balance) + '</span></div>' +
    '<div class="card stat"><span class="stat-label">\u4eca\u65e5\u8bf7\u6c42</span><span class="stat-value">' + stats.today_requests + '</span></div>' +
    '<div class="card stat"><span class="stat-label">\u4eca\u65e5\u6536\u5165</span><span class="stat-value">' + fmtMoney(stats.today_revenue) + '</span></div>';

  try {
    const channels = await api('/api/admin/channels');
    window._adminChannels = {};
    channels.forEach(c => { window._adminChannels[c.id] = c; });
    document.getElementById('channels-list').innerHTML = channels.length
      ? channels.map(c => '<div class="channel-item"><strong>' + c.name + '</strong> · ' + c.base_url + '<br>模型: ' + c.models + ' · 权重: ' + c.weight + ' · 状态: ' + c.status +
        ' <button class="btn btn-outline btn-sm" onclick="editChannelForm(' + c.id + ', window._adminChannels[' + c.id + '])">编辑</button>' +
        ' <button class="btn btn-outline btn-sm" onclick="deleteChannel(' + c.id + ')" style="color:var(--danger)">删除</button></div>').join('')
      : '<p class="muted-text">暂无渠道，请先添加上游</p>';
  } catch (e) {
    document.getElementById('channels-list').innerHTML = '<p class="muted-text">渠道加载失败</p>';
  }

  try {
    const pricing = await api('/api/admin/pricing');
    window._adminPricing = {};
    pricing.forEach(p => { window._adminPricing[p.id] = p; });
    document.getElementById('pricing-list-admin').innerHTML = pricing.length
<<<<<<< HEAD
      ? pricing.map(p => {
          // 计算折扣：本站价 / 官方价 × 100%
          let inputDisc = '', outputDisc = '';
          if (p.official_input_price > 0 && p.input_price > 0) {
            inputDisc = '（' + (p.input_price / p.official_input_price * 100).toFixed(0) + '%）';
          }
          if (p.official_output_price > 0 && p.output_price > 0) {
            outputDisc = '（' + (p.output_price / p.official_output_price * 100).toFixed(0) + '%）';
          }
          let officialHtml = '';
          if (p.official_input_price > 0 || p.official_output_price > 0) {
            officialHtml = '<br><span style="color:var(--muted);font-size:.8rem">官方价: 输入 ' + p.official_input_price + '/1K · 输出 ' + p.official_output_price + '/1K</span>';
          }
          return '<div class="pricing-item"><strong>' + p.model + '</strong>' +
            '<br>本站: 输入 <span style="color:#22c55e">' + p.input_price + '/1K</span>' + inputDisc +
            ' · 输出 <span style="color:#22c55e">' + p.output_price + '/1K</span>' + outputDisc +
            officialHtml +
            (p.cost_price > 0 ? ' · 成本: ' + p.cost_price + '/1K' : ' · 成本: 未设') +
            ' <button class="btn btn-outline btn-sm" onclick="editPricingForm(' + p.id + ', window._adminPricing[' + p.id + '])" style="margin-top:4px">编辑</button>' +
            ' <button class="btn btn-outline btn-sm" onclick="deletePricing(' + p.id + ')" style="margin-top:4px;color:var(--danger)">删除</button></div>';
        }).join('')
=======
      ? pricing.map(p =>
        '<div class="pricing-item"><strong>' + p.model + '</strong><br>输入: ' + p.input_price + '/1K · 输出: ' + p.output_price + '/1K' +
        ' <button class="btn btn-outline btn-sm" onclick="editPricingForm(' + p.id + ', window._adminPricing[' + p.id + '])" style="margin-top:4px">编辑</button>' +
        ' <button class="btn btn-outline btn-sm" onclick="deletePricing(' + p.id + ')" style="margin-top:4px;color:var(--danger)">删除</button></div>'
      ).join('')
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
      : '<p class="muted-text">暂无定价，请先添加</p>';
  } catch (e) {
    document.getElementById('pricing-list-admin').innerHTML = '<p class="muted-text">\u5b9a\u4ef7\u52a0\u8f7d\u5931\u8d25</p>';
  }

  try {
    const users = await api('/api/admin/users');
    document.getElementById('users-body').innerHTML = users.map(u =>
      '<tr><td>' + u.id + '</td><td>' + u.username + '</td><td>' + u.email + '</td><td>' + fmtMoney(u.balance) + '</td><td>' + (u.is_active ? '\u6b63\u5e38' : '\u7981\u7528') + '</td><td>' +
      '<button class="btn btn-primary btn-sm recharge-btn" data-user-id="' + u.id + '" data-username="' + escapeAttr(u.username) + '">\u5145\u503c</button> ' +
      (u.role !== 'admin' ? '<button class="btn btn-outline btn-sm toggle-btn" data-user-id="' + u.id + '">\u5207\u6362\u72b6\u6001</button>' : '') +
      '</td></tr>'
    ).join('');

    document.querySelectorAll('.recharge-btn').forEach(btn => {
      btn.onclick = () => showRechargeForm(parseInt(btn.dataset.userId, 10), btn.dataset.username);
    });
    document.querySelectorAll('.toggle-btn').forEach(btn => {
      btn.onclick = () => toggleUser(parseInt(btn.dataset.userId, 10));
    });
  } catch (e) {
    document.getElementById('users-body').innerHTML = '<tr><td colspan="6" style="color:var(--muted)">\u7528\u6237\u52a0\u8f7d\u5931\u8d25</td></tr>';
  }

  try {
    const usage = await api('/api/admin/usage');
    document.getElementById('admin-usage-body').innerHTML = usage.map(u =>
      '<tr><td>' + fmtTime(u.created_at) + '</td><td>' + u.user_id + '</td><td>' + u.model + '</td><td>' + u.total_tokens + '</td><td>' + fmtMoney(u.cost) + '</td><td>' + u.status + '</td></tr>'
    ).join('');
  } catch (e) {
    document.getElementById('admin-usage-body').innerHTML = '<tr><td colspan="6" style="color:var(--muted)">\u7528\u91cf\u52a0\u8f7d\u5931\u8d25</td></tr>';
  }

  // 加载兑换码列表
  try {
    const codes = await api('/api/admin/redeem-codes');
    document.getElementById('redeem-body').innerHTML = codes.length
      ? codes.map(c =>
          '<tr>' +
          '<td><code style="font-size:.75rem">' + c.code + '</code></td>' +
          '<td>' + fmtMoney(c.amount) + '</td>' +
          '<td>' + (c.is_used ? '<span style="color:var(--muted)">已使用</span>' : '<span style="color:var(--success)">未使用</span>') + '</td>' +
          '<td>' + (c.used_by || '-') + '</td>' +
          '<td>' + fmtTime(c.used_at) + '</td>' +
          '<td>' + (c.remark || '-') + '</td>' +
          '</tr>'
        ).join('')
      : '<tr><td colspan="6" style="color:var(--muted)">暂无兑换码，点击「生成兑换码」创建</td></tr>';
  } catch (e) {
    document.getElementById('redeem-body').innerHTML = '<tr><td colspan="6" style="color:var(--muted)">加载失败</td></tr>';
  }

  // 加载充值订单列表
  try {
    const orders = await api('/api/admin/recharge-orders');
    const statusLabel = { pending: '⏳ 待支付', submitted: '🔄 待审核', paid: '✅ 已到账', cancelled: '❌ 已取消' };
    const statusColor = { pending: 'var(--muted)', submitted: '#f59e0b', paid: '#22c55e', cancelled: 'var(--danger)' };
<<<<<<< HEAD
    const payLabel = { wechat: '微信扫码', alipay: '支付宝', wechat_pay: '微信支付' };
=======
    const payLabel = { wechat: '微信支付', alipay: '支付宝' };
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
    document.getElementById('orders-body').innerHTML = orders.length
      ? orders.map(o => {
          let actionHtml = '';
          if (o.status === 'submitted') {
            actionHtml =
              '<button class="btn btn-success btn-sm" onclick="verifyOrder(' + o.id + ', \'approve\')" style="margin-right:4px">确认到账</button>' +
              '<button class="btn btn-danger btn-sm" onclick="verifyOrder(' + o.id + ', \'reject\')">拒绝</button>';
          }
          return '<tr>' +
            '<td><code style="font-size:.75rem">' + o.order_no + '</code></td>' +
            '<td>' + o.user_id + '</td>' +
            '<td>' + fmtMoney(o.amount) + '</td>' +
            '<td>' + (payLabel[o.pay_method] || o.pay_method) + '</td>' +
            '<td><span style="color:' + (statusColor[o.status] || '') + '">' + (statusLabel[o.status] || o.status) + '</span></td>' +
            '<td>' + fmtTime(o.created_at) + '</td>' +
            '<td>' + (actionHtml || '-') + '</td>' +
            '</tr>';
        }).join('')
      : '<tr><td colspan="7" style="color:var(--muted)">暂无充值订单</td></tr>';
  } catch (e) {
    document.getElementById('orders-body').innerHTML = '<tr><td colspan="7" style="color:var(--muted)">加载失败</td></tr>';
  }

  // 加载平台收款码管理
  await loadPlatformQrcodes().catch(() => {});

  // 加载代理列表
  await loadAgents().catch(() => {});
  // 加载提现申请
  await loadWithdrawals().catch(() => {});
<<<<<<< HEAD

  // 加载降级映射
  try { await loadFallbacks(); } catch(e) {}
  // 加载毛利报告
  try { await loadMarginReport(); } catch(e) {}
=======
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
}

// ======= 订单审核 =======
async function verifyOrder(orderId, action) {
  const label = action === 'approve' ? '确认到账' : '拒绝';
  if (!confirm('确定要' + label + '该充值订单吗？')) return;
  try {
    const result = await api('/api/admin/recharge-orders/' + orderId + '/verify', {
      method: 'POST',
      body: JSON.stringify({ action, reason: '' }),
    });
    alert(result.message);
    await loadAdminPanel();
  } catch (err) {
    alert(err.message);
  }
}

// ======= 平台收款码管理 =======
const PLATFORM_AMOUNTS = [2, 5, 10, 20, 50, 100, 500];
const PLATFORM_METHODS = ['wechat', 'alipay'];

async function loadPlatformQrcodes() {
  const grid = document.getElementById('qrcode-grid');
  if (!grid) return;
  try {
    const qrcodes = await api('/api/admin/platform-qrcodes');
    const lookup = {};
    qrcodes.forEach(q => { lookup[q.pay_method + '_' + q.amount] = q.qrcode_path; });

    let html = '';
    PLATFORM_METHODS.forEach(method => {
      const methodLabel = method === 'wechat' ? '💚 微信' : '💙 支付宝';
      PLATFORM_AMOUNTS.forEach(amount => {
        const key = method + '_' + amount;
        const path = lookup[key] || '';
        html += '<div class="qrcode-slot" style="background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center">' +
          '<div style="font-weight:600;margin-bottom:8px">' + methodLabel + ' ¥' + amount + '</div>' +
          (path
            ? '<img src="' + path + '" style="width:100px;height:100px;object-fit:contain;border-radius:6px;margin-bottom:8px" onerror="this.style.display=\'none\'">'
            : '<div style="width:100px;height:100px;border:2px dashed var(--border);border-radius:6px;margin:0 auto 8px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:.75rem">未上传</div>') +
          '<div>' +
          '<input type="file" accept="image/png,image/jpeg,image/gif,image/webp" style="display:none" id="qrcode-input-' + key + '" onchange="uploadPlatformQrcode(\'' + method + '\',' + amount + ',this)">' +
          '<button class="btn btn-outline btn-sm" onclick="document.getElementById(\'qrcode-input-' + key + '\').click()">' + (path ? '更换' : '上传') + '</button>' +
          '</div>' +
          '</div>';
      });
    });
    grid.innerHTML = html;
  } catch (e) {
    grid.innerHTML = '<p style="color:var(--muted)">加载失败</p>';
  }
}

async function uploadPlatformQrcode(payMethod, amount, input) {
  const file = input.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('pay_method', payMethod);
  formData.append('amount', amount);
  try {
    const resp = await fetch('/api/admin/platform-qrcode', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getToken() },
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || '上传失败');
    }
    // 刷新显示 + 预加载缓存
    await loadPlatformQrcodes();
    // 刷新用户端缓存
    try {
      const qrcodes = await fetch('/api/platform-qrcodes').then(r => r.json());
      window._platformQrcodes = {};
      qrcodes.forEach(q => {
        window._platformQrcodes[q.pay_method + '_' + q.amount] = q.qrcode_path;
      });
    } catch (e) { /* 静默 */ }
  } catch (err) {
    alert(err.message);
  }
}

function closeModal() { document.getElementById('modal').style.display = 'none'; }

function escapeAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function showRechargeForm(userId, username) {
  document.getElementById('modal-title').textContent = '\u7ed9\u7528\u6237\u5145\u503c';
  document.getElementById('modal-body').innerHTML =
    '<p class="section-desc">\u7528\u6237\uff1a<strong>' + escapeAttr(username) + '</strong> (ID: ' + userId + ')</p>' +
    '<label>\u5145\u503c\u91d1\u989d\uff08\u5143\uff09</label><input id="rc-amount" type="number" step="0.01" min="0.01" value="10" autofocus>' +
    '<label>\u5907\u6ce8\uff08\u53ef\u9009\uff09</label><input id="rc-remark" placeholder="\u7ba1\u7406\u5458\u5145\u503c">';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '\u786e\u8ba4\u5145\u503c';
  document.getElementById('modal-submit').onclick = async () => {
    const amount = parseFloat(document.getElementById('rc-amount').value);
    const remark = document.getElementById('rc-remark').value.trim();
    if (!amount || amount <= 0) {
      alert('\u8bf7\u8f93\u5165\u6b63\u786e\u7684\u5145\u503c\u91d1\u989d');
      return;
    }
    try {
      const result = await api('/api/admin/recharge', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, amount, remark: remark || null }),
      });
      closeModal();
      await loadAdminPanel();
      alert('\u5145\u503c\u6210\u529f\uff01\u5f53\u524d\u4f59\u989d\uff1a' + fmtMoney(result.balance));
    } catch (err) {
      alert(err.message);
    }
  };
}

function showChannelForm() {
  document.getElementById('modal-title').textContent = '\u6dfb\u52a0\u4e0a\u6e38\u6e20\u9053';
  document.getElementById('modal-body').innerHTML =
    '<label>\u540d\u79f0</label><input id="ch-name" placeholder="OpenAI\u5b98\u65b9">' +
    '<label>Base URL</label><input id="ch-url" placeholder="https://api.openai.com">' +
    '<label>\u4e0a\u6e38 API Key</label><input id="ch-key" placeholder="sk-...">' +
    '<label>\u652f\u6301\u6a21\u578b\uff08\u9017\u53f7\u5206\u9694\uff0c* \u8868\u793a\u5168\u90e8\uff09</label><input id="ch-models" value="*">' +
    '<label>\u6743\u91cd</label><input id="ch-weight" type="number" value="100">';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '\u786e\u8ba4';
  document.getElementById('modal-submit').onclick = async () => {
    try {
      await api('/api/admin/channels', { method: 'POST', body: JSON.stringify({
        name: document.getElementById('ch-name').value,
        base_url: document.getElementById('ch-url').value,
        api_key: document.getElementById('ch-key').value,
        models: document.getElementById('ch-models').value,
        weight: parseInt(document.getElementById('ch-weight').value, 10) || 100,
      })});
      closeModal();
      await loadAdminPanel();
    } catch (err) { alert(err.message); }
  };
}

<<<<<<< HEAD
// ====== 模型定价：搜索 / 筛选 / 排序 / 渲染 ======

/** 预定义标签样式配置 */
const PRICING_TAGS = {
  '限免':   { bg: 'rgba(139,92,246,.2)',  color: '#a78bfa', icon: '🎁' },
  '特价':   { bg: 'rgba(239,68,68,.18)',  color: '#f87171', icon: '🔥' },
  '低价':   { bg: 'rgba(34,197,94,.18)',  color: '#4ade80', icon: '💰' },
  '优质':   { bg: 'rgba(245,158,11,.2)',  color: '#fbbf24', icon: '⭐' },
  '快速':   { bg: 'rgba(59,130,246,.18)', color: '#60a5fa', icon: '⚡' },
  '热门':   { bg: 'rgba(239,68,68,.18)',  color: '#f97316', icon: '🔥' },
  '推荐':   { bg: 'rgba(6,182,212,.18)',  color: '#22d3ee', icon: '👍' },
  '新上线': { bg: 'rgba(16,185,129,.18)', color: '#34d399', icon: '🆕' },
  '稳定':   { bg: 'rgba(107,114,128,.2)', color: '#9ca3af', icon: '🛡' },
  '多模态': { bg: 'rgba(168,85,247,.18)', color: '#c084fc', icon: '🎨' },
  '长文本': { bg: 'rgba(20,184,166,.18)', color: '#2dd4bf', icon: '📃' },
  '代码':   { bg: 'rgba(99,102,241,.18)', color: '#818cf8', icon: '💻' },
  '限时5折': { bg: 'rgba(239,68,68,.22)', color: '#ef4444', icon: '⏰' },
  '限时7折': { bg: 'rgba(249,115,22,.2)', color: '#fb923c', icon: '⏰' },
  '限时8折': { bg: 'rgba(251,146,60,.18)',color: '#fda44c', icon: '⏰' },
  '精选':   { bg: 'rgba(234,179,8,.18)',  color: '#eab308', icon: '💎' },
};

/** 渲染一组标签徽章 HTML */
function renderTagBadges(tags, size) {
  if (!tags || !tags.length) return '';
  const fs = size === 'sm' ? '.7rem' : '.75rem';
  const px = size === 'sm' ? '1px 5px' : '2px 7px';
  return tags.map(tag => {
    const cfg = PRICING_TAGS[tag] || { bg: 'rgba(255,255,255,.08)', color: '#9ca3af', icon: '' };
    return '<span style="display:inline-flex;align-items:center;gap:3px;background:' + cfg.bg + ';color:' + cfg.color +
      ';border-radius:4px;padding:' + px + ';font-size:' + fs + ';font-weight:600;white-space:nowrap">' +
      (cfg.icon ? '<span>' + cfg.icon + '</span>' : '') + tag + '</span>';
  }).join(' ');
}


function detectModelSeries(model) {
  const m = model.toLowerCase();
  if (m.includes('gpt') || m.startsWith('o1') || m.startsWith('o3') || m.startsWith('o4') || m.includes('text-davinci')) return 'GPT';
  if (m.includes('claude')) return 'Claude';
  if (m.includes('deepseek')) return 'DeepSeek';
  if (m.includes('gemini') || m.includes('gemma')) return 'Gemini';
  if (m.includes('qwen') || m.includes('通义')) return 'Qwen';
  if (m.includes('llama') || m.includes('meta-llama')) return 'Llama';
  if (m.includes('mistral') || m.includes('mixtral')) return 'Mistral';
  if (m.includes('yi-') || m.includes('零一万物')) return '零一';
  if (m.includes('moonshot') || m.includes('kimi')) return 'Kimi';
  if (m.includes('baichuan')) return '百川';
  if (m.includes('spark') || m.includes('xinghuo')) return '讯飞';
  if (m.includes('ernie') || m.includes('wenxin')) return '文心';
  if (m.includes('hunyuan')) return '混元';
  if (m.includes('minimax')) return 'MiniMax';
  return '其他';
}

/** 计算折扣比例（相对官方输入价） */
function calcDiscount(p) {
  if (p.official_input_price > 0 && p.input_price > 0) {
    return p.input_price / p.official_input_price;
  }
  return null;
}

/** 渲染折扣徽章 HTML */
function discountBadge(p) {
  const ratio = calcDiscount(p);
  if (ratio === null) return '<span style="color:var(--muted);font-size:.8rem">-</span>';
  const pct = (ratio * 100).toFixed(0);
  if (ratio < 1) return '<span style="background:rgba(34,197,94,.15);color:#22c55e;border-radius:4px;padding:2px 7px;font-size:.8rem;font-weight:600">' + pct + '%</span>';
  if (ratio === 1) return '<span style="background:rgba(245,158,11,.12);color:#f59e0b;border-radius:4px;padding:2px 7px;font-size:.8rem">平价</span>';
  return '<span style="background:rgba(239,68,68,.12);color:var(--danger);border-radius:4px;padding:2px 7px;font-size:.8rem">' + pct + '%</span>';
}

/** 构建系列筛选 chips */
function buildPricingSeriesChips(pricing) {
  const seriesSet = new Set(pricing.map(p => detectModelSeries(p.model)));
  const series = ['全部', ...Array.from(seriesSet).sort()];
  const container = document.getElementById('pricing-series-chips');
  if (!container) return;
  container.innerHTML = series.map((s, i) =>
    '<button class="pricing-chip' + (i === 0 ? ' pricing-chip-active' : '') + '" data-series="' + s + '" onclick="selectPricingChip(this)">' + s + '</button>'
  ).join('');
}

/** 点击系列 chip */
function selectPricingChip(el) {
  document.querySelectorAll('.pricing-chip').forEach(b => b.classList.remove('pricing-chip-active'));
  el.classList.add('pricing-chip-active');
  filterPricing();
}

/** 切换视图（table / card） */
function switchPricingView(view) {
  window._pricingView = view;
  const tv = document.getElementById('pricing-table-view');
  const cv = document.getElementById('pricing-card-view');
  const btnT = document.getElementById('pricing-view-table');
  const btnC = document.getElementById('pricing-view-card');
  if (view === 'table') {
    if (tv) tv.style.display = '';
    if (cv) cv.style.display = 'none';
    if (btnT) { btnT.style.background = 'var(--primary)'; btnT.style.color = '#fff'; }
    if (btnC) { btnC.style.background = 'var(--surface)'; btnC.style.color = 'var(--muted)'; }
  } else {
    if (tv) tv.style.display = 'none';
    if (cv) cv.style.display = '';
    if (btnT) { btnT.style.background = 'var(--surface)'; btnT.style.color = 'var(--muted)'; }
    if (btnC) { btnC.style.background = 'var(--primary)'; btnC.style.color = '#fff'; }
  }
  filterPricing();
}

/** 点击列头快速设置排序 */
function setPricingSort(key) {
  const sel = document.getElementById('pricing-sort');
  if (!sel) return;
  const cur = sel.value;
  // 同一列再次点击切换 asc/desc
  if (cur === key + '_asc') {
    sel.value = key + '_desc';
  } else if (cur === key + '_desc') {
    sel.value = key + '_asc';
  } else {
    sel.value = key + '_asc';
  }
  filterPricing();
}

/** 主过滤 + 排序 + 渲染函数 */
function filterPricing() {
  const q = (document.getElementById('pricing-search')?.value || '').toLowerCase().trim();
  const sort = document.getElementById('pricing-sort')?.value || '';
  const activeChip = document.querySelector('.pricing-chip-active');
  const activeSeries = activeChip?.dataset.series || '全部';

  let data = (window._pricingData || []).filter(p => p.is_active !== false);

  // 关键词搜索
  if (q) data = data.filter(p => p.model.toLowerCase().includes(q) || (p.description || '').toLowerCase().includes(q));

  // 系列筛选
  if (activeSeries !== '全部') data = data.filter(p => detectModelSeries(p.model) === activeSeries);

  // 排序
  if (sort) {
    const [field, dir] = sort.split('_');
    const asc = dir === 'asc';
    if (field === 'input') data = [...data].sort((a, b) => asc ? a.input_price - b.input_price : b.input_price - a.input_price);
    else if (field === 'output') data = [...data].sort((a, b) => asc ? a.output_price - b.output_price : b.output_price - a.output_price);
    else if (field === 'discount') data = [...data].sort((a, b) => {
      const da = calcDiscount(a) ?? 999, db = calcDiscount(b) ?? 999;
      return asc ? da - db : db - da;
    });
    else if (field === 'name') data = [...data].sort((a, b) => a.model.localeCompare(b.model));
  }

  // 更新统计
  const total = (window._pricingData || []).length;
  const stat = document.getElementById('pricing-stat');
  if (stat) {
    stat.textContent = data.length === total
      ? '共 ' + total + ' 个模型'
      : '显示 ' + data.length + ' 个（共 ' + total + ' 个）';
  }

  const view = window._pricingView || 'table';
  if (view === 'table') renderPricingTable(data);
  else renderPricingCards(data);
}

/** 表格视图渲染 */
function renderPricingTable(pricing) {
  const tbody = document.getElementById('pricing-body');
  if (!tbody) return;
  if (!pricing.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:32px 0">无匹配模型，请调整搜索条件</td></tr>';
    return;
  }
  tbody.innerHTML = pricing.map(p => {
    const offIn  = p.official_input_price  > 0 ? p.official_input_price  : '<span style="color:var(--muted)">-</span>';
    const offOut = p.official_output_price > 0 ? p.official_output_price : '<span style="color:var(--muted)">-</span>';
    const series = detectModelSeries(p.model);
    const seriesColor = { GPT:'#10a37f', Claude:'#b87c3f', DeepSeek:'#4c9aff', Gemini:'#4285f4', Qwen:'#6366f1', Llama:'#a855f7', Mistral:'#f97316' };
    const dot = seriesColor[series]
      ? '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:' + seriesColor[series] + ';margin-right:5px;vertical-align:middle"></span>'
      : '';
    const tagsHtml = renderTagBadges(p.tags, 'sm');
    return '<tr>' +
      '<td style="max-width:220px">' + dot + '<code style="font-size:.82rem;word-break:break-all">' + p.model + '</code>' +
      (tagsHtml ? '<br><span style="display:inline-flex;flex-wrap:wrap;gap:3px;margin-top:3px">' + tagsHtml + '</span>' : '') +
      (p.description ? '<br><span style="color:var(--muted);font-size:.75rem">' + p.description + '</span>' : '') + '</td>' +
      '<td style="text-align:right;color:var(--muted);font-size:.875rem">' + offIn + '</td>' +
      '<td style="text-align:right;color:var(--muted);font-size:.875rem">' + offOut + '</td>' +
      '<td style="text-align:right;color:#22c55e;font-weight:600">' + p.input_price + '</td>' +
      '<td style="text-align:right;color:#22c55e;font-weight:600">' + p.output_price + '</td>' +
      '<td style="text-align:center">' + discountBadge(p) + '</td>' +
      '<td style="color:var(--muted);font-size:.8rem">' + (p.description || '-') + '</td>' +
      '</tr>';
  }).join('');
}

/** 卡片视图渲染 */
function renderPricingCards(pricing) {
  const container = document.getElementById('pricing-cards');
  if (!container) return;
  if (!pricing.length) {
    container.innerHTML = '<p style="color:var(--muted);text-align:center;padding:40px 0;grid-column:1/-1">无匹配模型，请调整搜索条件</p>';
    return;
  }
  const seriesColor = { GPT:'#10a37f', Claude:'#b87c3f', DeepSeek:'#4c9aff', Gemini:'#4285f4', Qwen:'#6366f1', Llama:'#a855f7', Mistral:'#f97316', Kimi:'#00a6ff', MiniMax:'#ff6b6b' };
  container.innerHTML = pricing.map(p => {
    const series = detectModelSeries(p.model);
    const color = seriesColor[series] || '#6b7280';
    const ratio = calcDiscount(p);
    const discHtml = ratio !== null
      ? (ratio < 1
          ? '<span style="background:rgba(34,197,94,.15);color:#22c55e;border-radius:20px;padding:2px 8px;font-size:.75rem;font-weight:600">' + (ratio * 100).toFixed(0) + '% 折</span>'
          : '<span style="background:rgba(245,158,11,.12);color:#f59e0b;border-radius:20px;padding:2px 8px;font-size:.75rem">平价</span>')
      : '';
    return '<div style="border:1px solid var(--border);border-radius:12px;padding:16px;background:var(--surface);position:relative;overflow:hidden;transition:box-shadow .2s" onmouseenter="this.style.boxShadow=\'0 4px 20px rgba(0,0,0,.25)\'" onmouseleave="this.style.boxShadow=\'none\'">' +
      '<div style="position:absolute;top:0;left:0;right:0;height:3px;background:' + color + '"></div>' +
      '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;gap:6px">' +
        '<code style="font-size:.78rem;word-break:break-all;flex:1;color:var(--text)">' + p.model + '</code>' +
        discHtml +
      '</div>' +
      (p.tags && p.tags.length ? '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px">' + renderTagBadges(p.tags) + '</div>' : '<div style="margin-bottom:10px"></div>') +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">' +
        '<div style="background:rgba(34,197,94,.07);border-radius:8px;padding:8px;text-align:center">' +
          '<div style="font-size:.7rem;color:var(--muted);margin-bottom:2px">本站输入</div>' +
          '<div style="font-weight:700;color:#22c55e;font-size:.95rem">¥' + p.input_price + '</div>' +
          (p.official_input_price > 0 ? '<div style="font-size:.68rem;color:var(--muted)">官方 ¥' + p.official_input_price + '</div>' : '') +
        '</div>' +
        '<div style="background:rgba(34,197,94,.07);border-radius:8px;padding:8px;text-align:center">' +
          '<div style="font-size:.7rem;color:var(--muted);margin-bottom:2px">本站输出</div>' +
          '<div style="font-weight:700;color:#22c55e;font-size:.95rem">¥' + p.output_price + '</div>' +
          (p.official_output_price > 0 ? '<div style="font-size:.68rem;color:var(--muted)">官方 ¥' + p.official_output_price + '</div>' : '') +
        '</div>' +
      '</div>' +
      (p.description ? '<p style="font-size:.75rem;color:var(--muted);margin:0;line-height:1.4">' + p.description + '</p>' : '') +
      '<div style="margin-top:8px"><span style="display:inline-block;background:rgba(255,255,255,.06);color:' + color + ';border-radius:4px;padding:1px 7px;font-size:.72rem">' + series + '</span></div>' +
      '</div>';
  }).join('');
}

/** 构建标签多选器 HTML（用于管理表单） */
function buildTagPickerHtml(selectedTags) {
  const sel = selectedTags || [];
  const presets = Object.keys(PRICING_TAGS);
  const pickerBtns = presets.map(tag => {
    const cfg = PRICING_TAGS[tag];
    const isSelected = sel.includes(tag);
    return '<button type="button" class="tag-picker-btn' + (isSelected ? ' tag-picker-selected' : '') + '" data-tag="' + tag + '"' +
      ' style="padding:4px 10px;border-radius:6px;border:1px solid ' + (isSelected ? cfg.color : 'var(--border)') + ';' +
      'background:' + (isSelected ? cfg.bg : 'transparent') + ';color:' + (isSelected ? cfg.color : 'var(--muted)') + ';' +
      'cursor:pointer;font-size:.8rem;transition:all .15s" onclick="toggleTagPicker(this)">' +
      cfg.icon + ' ' + tag + '</button>';
  }).join('');
  return '<label style="margin-top:12px">模型标签（点击多选，或输入自定义标签）</label>' +
    '<div id="tag-picker" style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0">' + pickerBtns + '</div>' +
    '<div style="display:flex;gap:8px;margin-top:6px">' +
      '<input id="pr-custom-tag" placeholder="自定义标签，按回车添加" style="flex:1;font-size:.85rem" onkeydown="if(event.key===\'Enter\'){event.preventDefault();addCustomPricingTag();}">' +
      '<button type="button" class="btn btn-outline btn-sm" onclick="addCustomPricingTag()">+ 添加</button>' +
    '</div>';
}

/** 切换标签选中状态 */
function toggleTagPicker(btn) {
  const tag = btn.dataset.tag;
  const cfg = PRICING_TAGS[tag] || { bg: 'rgba(255,255,255,.08)', color: '#9ca3af', icon: '' };
  const isNowSelected = !btn.classList.contains('tag-picker-selected');
  btn.classList.toggle('tag-picker-selected', isNowSelected);
  btn.style.borderColor = isNowSelected ? cfg.color : 'var(--border)';
  btn.style.background  = isNowSelected ? cfg.bg    : 'transparent';
  btn.style.color       = isNowSelected ? cfg.color : 'var(--muted)';
}

/** 添加自定义标签 */
function addCustomPricingTag() {
  const input = document.getElementById('pr-custom-tag');
  const tag = (input?.value || '').trim();
  if (!tag) return;
  // 检查是否已存在（预设或自定义）
  const exists = document.querySelector('#tag-picker [data-tag="' + tag + '"]');
  if (exists) { toggleTagPicker(exists); input.value = ''; return; }
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.dataset.tag = tag;
  btn.className = 'tag-picker-btn tag-picker-selected';
  btn.style.cssText = 'padding:4px 10px;border-radius:6px;border:1px solid #9ca3af;background:rgba(255,255,255,.08);color:#9ca3af;cursor:pointer;font-size:.8rem;transition:all .15s';
  btn.textContent = tag;
  btn.onclick = function() { toggleTagPicker(this); };
  document.getElementById('tag-picker').appendChild(btn);
  input.value = '';
}

/** 读取当前已选标签列表 */
function getSelectedPricingTags() {
  return Array.from(document.querySelectorAll('#tag-picker .tag-picker-selected')).map(b => b.dataset.tag);
}

// ====== API Key 管理：模型绑定 ======

/** 获取所有模型定价数据（供模型选择器使用） */
function getAllModels() {
  return (window._pricingData || []).filter(p => p.is_active !== false);
}

/** 构建模型选择器 UI */
function buildModelSelector(selectedModels) {
  const allModels = getAllModels();
  if (!allModels.length) return '<p style="color:var(--muted);font-size:.85rem">暂无可用模型</p>';

  // 按系列分组
  const groups = {};
  allModels.forEach(m => {
    const series = detectModelSeries(m.model);
    if (!groups[series]) groups[series] = [];
    groups[series].push(m);
  });

  const sortedGroups = Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0]));

  let html = '<div style="margin-top:10px">';
  html += '<label style="font-size:.85rem;color:var(--muted)">选择允许调用的模型（留空表示不限）</label>';
  html += '<div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap">';
  html += '<button type="button" class="btn btn-outline btn-sm" onclick="selectAllModels()" style="font-size:.8rem">全选</button>';
  html += '<button type="button" class="btn btn-outline btn-sm" onclick="clearAllModels()" style="font-size:.8rem">清空</button>';
  html += '<button type="button" class="btn btn-outline btn-sm" onclick="switchTab(\'pricing\')" style="font-size:.8rem;border-color:var(--primary);color:var(--primary)">';
  html += '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:3px"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>查看定价</button>';
  html += '</div>';

  // 搜索框
  html += '<input id="model-selector-search" type="text" placeholder="搜索模型..." style="width:100%;padding:7px 10px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:.85rem;margin-bottom:8px;box-sizing:border-box" oninput="filterModelSelector()">';

  sortedGroups.forEach(([series, models]) => {
    html += '<details class="model-group" style="margin-bottom:8px">' +
      '<summary style="cursor:pointer;font-weight:600;font-size:.85rem;color:var(--text);padding:4px 0;user-select:none">' + series + ' <span style="color:var(--muted);font-weight:400">(' + models.length + ')</span></summary>' +
      '<div class="model-group-content" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;padding-left:8px">';
    models.forEach(m => {
      const isChecked = (selectedModels || []).includes(m.model) ? 'checked' : '';
      html += '<label style="display:flex;align-items:center;gap:4px;padding:4px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface);cursor:pointer;font-size:.82rem;transition:all .15s" data-model-name="' + m.model + '">' +
        '<input type="checkbox" value="' + m.model + '" ' + isChecked + ' onchange="updateModelSelectorPreview()" style="accent-color:var(--primary)">' +
        '<span style="font-family:monospace">' + m.model + '</span>' +
        '</label>';
    });
    html += '</div></details>';
  });

  html += '</div>';

  // 已选预览
  html += '<div id="model-selector-preview" style="margin-top:8px;padding:8px;background:rgba(99,102,241,.08);border-radius:6px;font-size:.82rem;color:var(--text);min-height:24px">' +
    (selectedModels && selectedModels.length ? '已选: ' + selectedModels.join(', ') : '<span style="color:var(--muted)">未选择任何模型（留空表示不限）</span>') +
    '</div>';

  return html;
}

/** 过滤模型选择器 */
function filterModelSelector() {
  const q = (document.getElementById('model-selector-search')?.value || '').toLowerCase();
  document.querySelectorAll('.model-group').forEach(group => {
    const labels = group.querySelectorAll('label[data-model-name]');
    let visibleCount = 0;
    labels.forEach(label => {
      const modelName = label.dataset.modelName.toLowerCase();
      const show = !q || modelName.includes(q);
      label.style.display = show ? '' : 'none';
      if (show) visibleCount++;
    });
    group.style.display = visibleCount > 0 ? '' : 'none';
    if (visibleCount > 0 && q) {
      const summary = group.querySelector('summary');
      if (summary) summary.innerHTML = summary.innerHTML.replace(/\(\d+\)/, '(' + visibleCount + ')');
    }
  });
}

/** 更新已选模型预览 */
function updateModelSelectorPreview() {
  const checked = Array.from(document.querySelectorAll('#model-selector-container input[type="checkbox"]:checked')).map(cb => cb.value);
  const preview = document.getElementById('model-selector-preview');
  if (preview) {
    preview.innerHTML = checked.length
      ? '<strong>已选:</strong> ' + checked.join(', ')
      : '<span style="color:var(--muted)">未选择任何模型（留空表示不限）</span>';
  }
}

/** 全选模型 */
function selectAllModels() {
  document.querySelectorAll('#model-selector-container input[type="checkbox"]').forEach(cb => cb.checked = true);
  updateModelSelectorPreview();
}

/** 清空模型 */
function clearAllModels() {
  document.querySelectorAll('#model-selector-container input[type="checkbox"]').forEach(cb => cb.checked = false);
  updateModelSelectorPreview();
}

/** 获取选中的模型列表 */
function getSelectedModels() {
  return Array.from(document.querySelectorAll('#model-selector-container input[type="checkbox"]:checked')).map(cb => cb.value);
}

/** 显示 API Key 表单（创建或编辑） */
function showApiKeyForm(id, current) {
  const isEdit = !!id;
  document.getElementById('api-key-modal-title').textContent = isEdit ? '编辑 API Key' : '创建 API Key';
  document.getElementById('api-key-modal-body').innerHTML =
    '<label>Key 名称</label><input id="ak-name" placeholder="my-app-key" value="' + (current ? escapeAttr(current.name) : 'key-' + Date.now()) + '">' +
    '<div id="model-selector-container">' + (current ? buildModelSelector(current.allowed_models) : buildModelSelector([])) + '</div>';
  document.getElementById('api-key-modal').style.display = 'flex';
  document.getElementById('api-key-modal-submit').textContent = isEdit ? '保存修改' : '创建';
  document.getElementById('api-key-modal-submit').onclick = async () => {
    try {
      const name = document.getElementById('ak-name').value.trim() || 'key-' + Date.now();
      const allowedModels = getSelectedModels();
      const url = isEdit ? '/api/user/api-keys/' + id : '/api/user/api-keys';
      const method = isEdit ? 'PUT' : 'POST';
      await api(url, { method, body: JSON.stringify({ name, allowed_models: allowedModels }) });
      closeApiKeyModal();
      await loadUserPanel();
    } catch (err) { alert('操作失败：' + err.message); }
  };
}

/** 关闭 API Key 模态框 */
function closeApiKeyModal() {
  document.getElementById('api-key-modal').style.display = 'none';
}

/** 删除 API Key */
async function deleteApiKey(id) {
  if (!confirm('确认删除此 API Key？删除后将无法调用任何模型。')) return;
  try {
    await api('/api/user/api-keys/' + id, { method: 'DELETE' });
    await loadUserPanel();
  } catch (err) {
    alert('删除失败：' + err.message);
  }
}

function showPricingForm() {
  document.getElementById('modal-title').textContent = '添加模型定价';
  document.getElementById('modal-body').innerHTML =
    '<label>模型名</label><input id="pr-model" placeholder="gpt-4o-mini" autofocus>' +
    '<hr style="border-color:var(--border);margin:12px 0">' +
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">' +
      '<div><label style="font-size:.8rem;color:#22c55e">本站输入价（元/1K）</label><input id="pr-in" type="number" step="0.0001" value="0.001"></div>' +
      '<div><label style="font-size:.8rem;color:var(--muted)">官方输入价（元/1K）</label><input id="pr-off-in" type="number" step="0.0001" value="0.0" placeholder="留空或0"></div>' +
      '<div><label style="font-size:.8rem;color:#22c55e">本站输出价（元/1K）</label><input id="pr-out" type="number" step="0.0001" value="0.004"></div>' +
      '<div><label style="font-size:.8rem;color:var(--muted)">官方输出价（元/1K）</label><input id="pr-off-out" type="number" step="0.0001" value="0.0" placeholder="留空或0"></div>' +
    '</div>' +
    '<label>上游成本价（元/1K tokens，用于毛利计算）</label><input id="pr-cost" type="number" step="0.0001" value="0.0" placeholder="留空或 0 表示未设置">' +
    '<label>说明（可选）</label><input id="pr-desc" placeholder="如：官方零售价">' +
    buildTagPickerHtml([]);
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '确认';
=======
function showPricingForm() {
  document.getElementById('modal-title').textContent = '\u6dfb\u52a0\u6a21\u578b\u5b9a\u4ef7';
  document.getElementById('modal-body').innerHTML =
    '<label>\u6a21\u578b\u540d</label><input id="pr-model" placeholder="gpt-4o-mini">' +
    '<label>\u8f93\u5165\u4ef7\u683c\uff08\u5143/1K tokens\uff09</label><input id="pr-in" type="number" step="0.0001" value="0.001">' +
    '<label>\u8f93\u51fa\u4ef7\u683c\uff08\u5143/1K tokens\uff09</label><input id="pr-out" type="number" step="0.0001" value="0.004">';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '\u786e\u8ba4';
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
  document.getElementById('modal-submit').onclick = async () => {
    try {
      await api('/api/admin/pricing', { method: 'POST', body: JSON.stringify({
        model: document.getElementById('pr-model').value,
        input_price: parseFloat(document.getElementById('pr-in').value),
        output_price: parseFloat(document.getElementById('pr-out').value),
<<<<<<< HEAD
        official_input_price: parseFloat(document.getElementById('pr-off-in').value) || 0,
        official_output_price: parseFloat(document.getElementById('pr-off-out').value) || 0,
        cost_price: parseFloat(document.getElementById('pr-cost').value) || 0,
        description: document.getElementById('pr-desc').value.trim() || null,
        tags: getSelectedPricingTags(),
=======
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
      })});
      closeModal();
      await loadAdminPanel();
    } catch (err) { alert(err.message); }
  };
}

async function deleteChannel(id) {
  if (!confirm('确认删除？')) return;
  try {
    await api('/api/admin/channels/' + id, { method: 'DELETE' });
    await loadAdminPanel();
  } catch (err) {
    alert('删除失败：' + err.message);
  }
}

// 编辑上游渠道
async function editChannelForm(id, current) {
  document.getElementById('modal-title').textContent = '编辑上游渠道';
  document.getElementById('modal-body').innerHTML =
    '<label>名称</label><input id="ch-name" value="' + escapeAttr(current.name) + '">' +
    '<label>Base URL</label><input id="ch-url" value="' + escapeAttr(current.base_url) + '">' +
    '<label>上游 API Key（留空保持不变）</label><input id="ch-key" placeholder="留空保持不变">' +
    '<label>支持模型（逗号分隔，* 表示全部）</label><input id="ch-models" value="' + escapeAttr(current.models) + '">' +
    '<label>权重</label><input id="ch-weight" type="number" value="' + current.weight + '">' +
    '<label>优先级</label><input id="ch-priority" type="number" value="' + (current.priority || 0) + '">' +
    '<label>状态</label><select id="ch-status"><option value="active"' + (current.status === 'active' ? ' selected' : '') + '>启用</option><option value="disabled"' + (current.status === 'disabled' ? ' selected' : '') + '>禁用</option></select>';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '保存修改';
  document.getElementById('modal-submit').onclick = async () => {
    const body = {
      name: document.getElementById('ch-name').value,
      base_url: document.getElementById('ch-url').value,
      models: document.getElementById('ch-models').value,
      weight: parseInt(document.getElementById('ch-weight').value, 10),
      priority: parseInt(document.getElementById('ch-priority').value, 10),
      status: document.getElementById('ch-status').value,
    };
    const apiKeyVal = document.getElementById('ch-key').value.trim();
    if (apiKeyVal) body.api_key = apiKeyVal;
    try {
      await api('/api/admin/channels/' + id, { method: 'PUT', body: JSON.stringify(body) });
      closeModal();
      await loadAdminPanel();
    } catch (err) { alert(err.message); }
  };
}

// 编辑模型定价
function editPricingForm(id, current) {
  document.getElementById('modal-title').textContent = '编辑模型定价';
  document.getElementById('modal-body').innerHTML =
    '<label>模型名</label><input id="pr-model" value="' + escapeAttr(current.model) + '">' +
<<<<<<< HEAD
    '<hr style="border-color:var(--border);margin:12px 0">' +
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">' +
      '<div><label style="font-size:.8rem;color:#22c55e">本站输入价（元/1K）</label><input id="pr-in" type="number" step="0.0001" value="' + current.input_price + '"></div>' +
      '<div><label style="font-size:.8rem;color:var(--muted)">官方输入价（元/1K）</label><input id="pr-off-in" type="number" step="0.0001" value="' + (current.official_input_price || 0) + '" placeholder="留空或0"></div>' +
      '<div><label style="font-size:.8rem;color:#22c55e">本站输出价（元/1K）</label><input id="pr-out" type="number" step="0.0001" value="' + current.output_price + '"></div>' +
      '<div><label style="font-size:.8rem;color:var(--muted)">官方输出价（元/1K）</label><input id="pr-off-out" type="number" step="0.0001" value="' + (current.official_output_price || 0) + '" placeholder="留空或0"></div>' +
    '</div>' +
    '<label>上游成本价（元/1K tokens，用于毛利计算）</label><input id="pr-cost" type="number" step="0.0001" value="' + (current.cost_price || 0) + '">' +
    '<label>说明</label><input id="pr-desc" value="' + escapeAttr(current.description || '') + '">' +
    buildTagPickerHtml(current.tags || []);
=======
    '<label>输入价格（元/1K tokens）</label><input id="pr-in" type="number" step="0.0001" value="' + current.input_price + '">' +
    '<label>输出价格（元/1K tokens）</label><input id="pr-out" type="number" step="0.0001" value="' + current.output_price + '">' +
    '<label>说明</label><input id="pr-desc" value="' + escapeAttr(current.description || '') + '">';
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '保存修改';
  document.getElementById('modal-submit').onclick = async () => {
    try {
      await api('/api/admin/pricing/' + id, { method: 'PUT', body: JSON.stringify({
        model: document.getElementById('pr-model').value,
        input_price: parseFloat(document.getElementById('pr-in').value),
        output_price: parseFloat(document.getElementById('pr-out').value),
<<<<<<< HEAD
        official_input_price: parseFloat(document.getElementById('pr-off-in').value) || 0,
        official_output_price: parseFloat(document.getElementById('pr-off-out').value) || 0,
        cost_price: parseFloat(document.getElementById('pr-cost').value) || 0,
        description: document.getElementById('pr-desc').value.trim() || null,
        tags: getSelectedPricingTags(),
=======
        description: document.getElementById('pr-desc').value.trim() || null,
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
      })});
      closeModal();
      await loadAdminPanel();
    } catch (err) { alert(err.message); }
  };
}

// 删除模型定价
async function deletePricing(id) {
  if (!confirm('确认删除此定价？')) return;
  try {
    await api('/api/admin/pricing/' + id, { method: 'DELETE' });
    await loadAdminPanel();
  } catch (err) {
    alert('删除失败：' + err.message);
  }
}

async function toggleUser(id) {
  try {
    await api('/api/admin/users/' + id + '/toggle', { method: 'POST' });
    await loadAdminPanel();
  } catch (err) {
    alert(err.message);
  }
}

function showRedeemForm() {
  document.getElementById('modal-title').textContent = '生成兑换码（卡密）';
  document.getElementById('modal-body').innerHTML =
    '<label>生成模式</label>' +
    '<div style="display:flex;gap:8px;margin-bottom:12px">' +
      '<button type="button" id="mode-amount" class="btn btn-primary btn-sm" onclick="switchRedeemMode(\'amount\')" style="flex:1">按金额（元）</button>' +
      '<button type="button" id="mode-tokens" class="btn btn-outline btn-sm" onclick="switchRedeemMode(\'tokens\')" style="flex:1">按 Token 量</button>' +
    '</div>' +
    '<div id="rd-amount-group"><label>面值（元）</label><input id="rd-amount" type="number" step="0.01" min="0.01" value="10" autofocus></div>' +
    '<div id="rd-tokens-group" style="display:none"><label>Token 数量</label><input id="rd-tokens" type="number" step="1000" min="1000" value="100000" placeholder="例如：100000（10万 Token）"><p class="field-hint">系统将根据默认模型价格自动换算为金额</p></div>' +
    '<label>生成数量（最多100张）</label><input id="rd-count" type="number" min="1" max="100" value="1">' +
    '<label>备注（可选）</label><input id="rd-remark" placeholder="如：内测用户充值卡">';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '生成';

  window._redeemMode = 'amount';

  document.getElementById('modal-submit').onclick = async () => {
    let amount;
    if (window._redeemMode === 'tokens') {
      const tokens = parseInt(document.getElementById('rd-tokens').value, 10);
      if (!tokens || tokens < 1000) { alert('Token 数量至少 1000'); return; }
      // 用默认模型价格换算：假设 0.004 元/1K tokens（中等价格）
      amount = (tokens / 1000) * 0.004;
      amount = Math.round(amount * 100) / 100; // 保留两位小数
    } else {
      amount = parseFloat(document.getElementById('rd-amount').value);
      if (!amount || amount <= 0) { alert('请输入正确的面值'); return; }
    }
    const count = parseInt(document.getElementById('rd-count').value, 10);
    const remark = document.getElementById('rd-remark').value.trim();
    if (!count || count < 1 || count > 100) { alert('数量需在 1~100 之间'); return; }
    try {
      const codes = await api('/api/admin/redeem-codes', {
        method: 'POST',
        body: JSON.stringify({ amount, count, remark: remark || null }),
      });
      closeModal();
      await loadAdminPanel();
      const codeList = codes.map(c => c.code).join('\n');
      const total = codes.length;
      const tokenVal = window._redeemMode === 'tokens' ? document.getElementById('rd-tokens').value : null;
      const label = window._redeemMode === 'tokens'
        ? ('约 ' + tokenVal + ' Token（' + fmtMoney(amount) + '）')
        : fmtMoney(amount);
      alert('生成成功！共 ' + total + ' 张，每张价值 ' + label + '。\n\n兑换码列表已在下方表格中显示。\n\n' + (total <= 10 ? '快速复制：\n' + codeList : '（超过10张，请从表格中复制）'));
    } catch (err) {
      alert(err.message);
    }
  };
}

function switchRedeemMode(mode) {
  window._redeemMode = mode;
  document.getElementById('mode-amount').className = mode === 'amount' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm';
  document.getElementById('mode-tokens').className = mode === 'tokens' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm';
  document.getElementById('rd-amount-group').style.display = mode === 'amount' ? 'block' : 'none';
  document.getElementById('rd-tokens-group').style.display = mode === 'tokens' ? 'block' : 'none';
}

// ======= 工具接入教程 Tab 切换 =======
function showTool(name, btn) {
  document.querySelectorAll('.tool-guide').forEach(el => el.style.display = 'none');
  // 仅清除工具教程区的 tab，不影响充值 tab
  if (btn) {
    btn.closest('.tool-tabs').querySelectorAll('.tool-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  const guide = document.getElementById('tool-' + name);
  if (guide) guide.style.display = 'block';
}

// ======= 通用复制文本函数（带视觉反馈） =======
async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const origHTML = btn.innerHTML;
    btn.innerHTML = '已复制 ✓';
    btn.style.color = 'var(--success)';
    setTimeout(() => { btn.innerHTML = origHTML; btn.style.color = ''; }, 1500);
  } catch {
    // 降级方案：用 prompt 让用户手动复制
    const input = document.createElement('textarea');
    input.value = text;
    input.style.position = 'fixed';
    input.style.left = '-9999px';
    document.body.appendChild(input);
    input.select();
    try { document.execCommand('copy'); btn.innerHTML = '已复制 ✓'; btn.style.color = 'var(--success)';
      setTimeout(() => { btn.innerHTML = '复制'; btn.style.color = ''; }, 1500); }
    catch { prompt('请手动复制：', text); }
    document.body.removeChild(input);
  }
}

// ======= 复制接入配置字段 =======
function copyField(elId, btn) {
  const text = document.getElementById(elId).textContent.trim();
  copyText(text, btn);
}

function updateCodeExample(apiKey, baseUrl) {
  const codeEl = document.getElementById('code-example');
  if (!codeEl) return;
  codeEl.textContent =
    '# 先安装：pip install openai\n' +
    'from openai import OpenAI\n\n' +
    'client = OpenAI(\n' +
    '    api_key="' + apiKey + '",\n' +
    '    base_url="' + baseUrl + '"\n' +
    ')\n\n' +
    'response = client.chat.completions.create(\n' +
    '    model="输入你需要的模型",\n' +
    '    messages=[{"role": "user", "content": "你好！"}]\n' +
    ')\n' +
    'print(response.choices[0].message.content)';
}

<<<<<<< HEAD
  // ======= 充电 Tab 切换（默认支付宝）=======
function switchRechargeTab(tab, btn) {
  document.querySelectorAll('.recharge-panel').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.recharge-tabs .tool-tab').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('recharge-' + tab);
  if (panel) panel.style.display = 'block';
  if (btn) btn.classList.add('active');
  document.getElementById('redeem-msg').textContent = '';
  if (document.getElementById('wechat-msg')) document.getElementById('wechat-msg').textContent = '';
  if (document.getElementById('alipay-msg')) document.getElementById('alipay-msg').textContent = '';
}

// ====== 微信 Native 支付 ======
window._wechatOrderNo = null;
window._wechatPollTimer = null;

function getWechatAmount() {
  const input = document.getElementById('wechat-amount-input');
  if (!input) return null;
  const val = parseFloat(input.value);
  return (isNaN(val) || val <= 0) ? null : val;
}

function handleWechatAmountInput() {
  const amount = getWechatAmount();
  const btn = document.getElementById('wechat-pay-btn');
  // 清除预设按钮选中状态
  document.querySelectorAll('.wechat-amount-btn').forEach(b => b.classList.remove('selected'));
  if (amount && btn) {
    btn.disabled = false;
    btn.textContent = '去微信支付 ¥' + amount.toFixed(2);
  } else if (btn) {
    btn.disabled = true;
    btn.textContent = '请输入充值金额';
  }
}

function selectWechatAmount(amount) {
  const input = document.getElementById('wechat-amount-input');
  if (input) { input.value = amount; }
  document.querySelectorAll('.wechat-amount-btn').forEach(b => {
    b.classList.toggle('selected', parseFloat(b.dataset.amount) === amount);
  });
  const btn = document.getElementById('wechat-pay-btn');
  if (btn) { btn.disabled = false; btn.textContent = '去微信支付 ¥' + amount.toFixed(2); }
}

async function createWechatPayment() {
  const amount = getWechatAmount();
  const msg = document.getElementById('wechat-msg');
  const btn = document.getElementById('wechat-pay-btn');
  if (!amount) { msg.textContent = '请输入有效的充值金额（最低 ¥1）'; return; }
  msg.textContent = '';
  msg.style.color = 'var(--danger)';
  if (btn) { btn.disabled = true; btn.textContent = '正在创建支付订单...'; }
  try {
    const result = await api('/api/payment/wechat/create', {
      method: 'POST',
      body: JSON.stringify({ amount: amount }),
    });
    window._wechatOrderNo = result.order_no;

    // 显示弹窗
    document.getElementById('payment-info').textContent = '请使用微信扫描下方二维码完成支付';
    document.getElementById('qr-amount-display').textContent = '¥' + amount.toFixed(2);
    document.getElementById('qr-order-no').textContent = '订单号：' + result.order_no;
    document.getElementById('qr-status-hint').textContent = '支付成功后自动到账';
    document.getElementById('pay-error-msg').textContent = '';

    // 生成二维码
    const qrImg = document.getElementById('qr-wechat-image');
    const qrLoading = document.getElementById('qr-wechat-loading');
    if (qrImg && qrLoading) {
      qrLoading.style.display = 'block';
      qrImg.style.display = 'none';
      qrImg.src = '/api/payment/qrcode?data=' + encodeURIComponent(result.code_url);
      qrImg.onload = function() {
        qrLoading.style.display = 'none';
        qrImg.style.display = 'block';
      };
      qrImg.onerror = function() {
        qrLoading.innerHTML = '<span style="font-size:3rem">❌</span><p style="margin-top:8px;color:var(--danger)">二维码生成失败</p>';
      };
    }

    document.getElementById('payment-modal').style.display = 'flex';

    // 开始轮询支付状态
    startPollWechatOrder(result.order_no);

    if (btn) { btn.disabled = false; btn.textContent = '去微信支付 ¥' + amount; }
  } catch (err) {
    msg.textContent = err.message || '支付创建失败，请稍后重试';
    if (btn) { btn.disabled = false; btn.textContent = '去微信支付 ¥' + amount; }
  }
}

function startPollWechatOrder(orderNo) {
  if (window._wechatPollTimer) clearInterval(window._wechatPollTimer);
  let pollCount = 0;
  const maxPolls = 120; // 最多轮询 2 分钟
  window._wechatPollTimer = setInterval(async () => {
    pollCount++;
    try {
      const result = await api('/api/payment/order/' + orderNo);
      if (result.status === 'paid') {
        clearInterval(window._wechatPollTimer);
        window._wechatPollTimer = null;
        document.getElementById('qr-status-hint').textContent = '✅ 支付成功！余额已到账';
        document.getElementById('qr-status-hint').style.color = 'var(--success)';
        // 1 秒后关闭弹窗并刷新
        setTimeout(() => {
          closePaymentModal();
          loadUserPanel();
        }, 1500);
        return;
      }
      if (pollCount >= maxPolls) {
        clearInterval(window._wechatPollTimer);
        window._wechatPollTimer = null;
        document.getElementById('qr-status-hint').textContent = '⏰ 等待超时，请确认是否已支付。关闭后可查看充值记录';
        document.getElementById('qr-status-hint').style.color = 'var(--warning,#f59e0b)';
      }
    } catch (e) {
      // 网络失败不中断轮询
    }
  }, 2000);
}

function closePaymentModal() {
  document.getElementById('payment-modal').style.display = 'none';
  window._wechatOrderNo = null;
  if (window._wechatPollTimer) {
    clearInterval(window._wechatPollTimer);
    window._wechatPollTimer = null;
  }
  // 重置二维码图片
  const qrImg = document.getElementById('qr-wechat-image');
  const qrLoading = document.getElementById('qr-wechat-loading');
  if (qrImg) { qrImg.src = ''; qrImg.style.display = 'none'; }
  if (qrLoading) qrLoading.style.display = 'block';
  document.getElementById('qr-status-hint').style.color = 'var(--muted)';
}

// ====== 支付宝在线支付 ======

function getAlipayAmount() {
  const input = document.getElementById('alipay-amount-input');
  if (!input) return null;
  const val = parseFloat(input.value);
  return (isNaN(val) || val <= 0) ? null : val;
}

function handleAlipayAmountInput() {
  const amount = getAlipayAmount();
  const btn = document.getElementById('alipay-pay-btn');
  document.querySelectorAll('.alipay-amount-btn').forEach(b => b.classList.remove('selected'));
  if (amount && btn) {
    btn.disabled = false;
    btn.textContent = '去支付宝支付 ¥' + amount.toFixed(2);
  } else if (btn) {
    btn.disabled = true;
    btn.textContent = '请输入充值金额';
  }
}

function selectAlipayAmount(amount) {
  const input = document.getElementById('alipay-amount-input');
  if (input) { input.value = amount; }
  document.querySelectorAll('.alipay-amount-btn').forEach(b => {
    b.classList.toggle('selected', parseFloat(b.dataset.amount) === amount);
  });
  const btn = document.getElementById('alipay-pay-btn');
  if (btn) { btn.disabled = false; btn.textContent = '去支付宝支付 ¥' + amount.toFixed(2); }
}

async function createAlipayPayment() {
  const amount = getAlipayAmount();
  const msg = document.getElementById('alipay-msg');
  const btn = document.getElementById('alipay-pay-btn');
  if (!amount) { msg.textContent = '请输入有效的充值金额（最低 ¥1）'; return; }
  msg.textContent = '';
  msg.style.color = 'var(--danger)';
  if (btn) { btn.disabled = true; btn.textContent = '正在跳转支付宝...'; }
  try {
    const result = await api('/api/payment/alipay/create', {
      method: 'POST',
      body: JSON.stringify({ amount: amount }),
    });
    if (result.pay_url) {
      msg.style.color = 'var(--success)';
      msg.textContent = '正在跳转到支付宝支付页面...';
      window.location.href = result.pay_url;
    } else {
      msg.textContent = '获取支付链接失败';
      if (btn) { btn.disabled = false; btn.textContent = '去支付宝支付 ¥' + amount; }
    }
  } catch (err) {
    msg.textContent = err.message || '支付创建失败，请稍后重试';
    if (btn) { btn.disabled = false; btn.textContent = '去支付宝支付 ¥' + amount; }
=======
// ======= 充值 Tab 切换 =======
function switchRechargeTab(tab, btn) {
  document.querySelectorAll('.recharge-panel').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.recharge-tabs .tool-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('recharge-' + tab).style.display = 'block';
  if (btn) btn.classList.add('active');
  document.getElementById('redeem-msg').textContent = '';
}

// ======= 选择支付方式 =======
function selectPayMethod(method) {
  window._selectedPayMethod = method;
  document.getElementById('pay-wechat').className = method === 'wechat' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm';
  document.getElementById('pay-alipay').className = method === 'alipay' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm';
}

// ======= 选择充值金额（固定面额） =======
function selectScanAmount(amount) {
  window._selectedScanAmount = amount;
  document.getElementById('scan-amount').value = amount;
  // 高亮选中的按钮
  document.querySelectorAll('.amount-btn').forEach(b => {
    b.classList.toggle('selected', parseInt(b.dataset.amount) === amount);
  });
  // 启用生成按钮
  const btn = document.getElementById('create-order-btn');
  if (btn) { btn.disabled = false; btn.textContent = '生成 ¥' + amount + ' 支付二维码'; }
}

// ======= 关闭支付弹窗 =======
function closePaymentModal() {
  document.getElementById('payment-modal').style.display = 'none';
  window._currentOrderNo = null;
}

// ======= 确认支付 — 提交管理员审核 =======
async function confirmPayment() {
  if (!window._currentOrderNo) {
    alert('未找到订单信息，请重新生成');
    return;
  }
  const btn = document.getElementById('confirm-pay-btn');
  const payMsg = document.getElementById('pay-error-msg');
  if (payMsg) { payMsg.textContent = ''; payMsg.style.color = 'var(--danger)'; }
  if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
  try {
    await api('/api/user/recharge-order/' + window._currentOrderNo + '/confirm', {
      method: 'POST',
    });
    document.getElementById('payment-modal').style.display = 'none';
    window._currentOrderNo = null;
    const msg = document.getElementById('redeem-msg');
    msg.style.color = '#f59e0b';
    msg.textContent = '支付凭证已提交，等待管理员审核到账（通常 5-30 分钟）';
  } catch (err) {
    if (payMsg) { payMsg.textContent = err.message; }
    else { alert(err.message); }
    if (btn) { btn.disabled = false; btn.textContent = '✅ 我已支付完成'; }
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
  }
}

// ============================================================
//  用户端 - 代理中心
// ============================================================

async function loadAgentInfo() {
  _wdUseNewQrcode = false;  // 每次刷新代理信息时重置
  const panels = ['agent-no-apply', 'agent-pending', 'agent-rejected', 'agent-disabled', 'agent-approved'];
  panels.forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });

  let agent = null;
  try {
    agent = await api('/api/user/agent/info');
  } catch (err) {
    // 404 → 未申请
    if (err.message && (err.message.includes('尚未申请') || err.message.includes('404'))) {
      const el = document.getElementById('agent-no-apply');
      if (el) el.style.display = 'block';
      return;
    }
  }
  if (!agent) {
    const el = document.getElementById('agent-no-apply');
    if (el) el.style.display = 'block';
    return;
  }

  if (agent.status === 'pending') {
    const el = document.getElementById('agent-pending');
    if (el) el.style.display = 'block';
  } else if (agent.status === 'rejected') {
    const el = document.getElementById('agent-rejected');
    if (el) el.style.display = 'block';
  } else if (agent.status === 'disabled') {
    const el = document.getElementById('agent-disabled');
    if (el) el.style.display = 'block';
  } else if (agent.status === 'approved') {
    const el = document.getElementById('agent-approved');
    if (el) el.style.display = 'block';

    // 填充统计
    const avail = document.getElementById('agent-available');
    const total = document.getElementById('agent-total');
    if (avail) avail.textContent = fmtMoney(agent.available_commission);
    if (total) total.textContent = fmtMoney(agent.total_commission);

    // 填充邀请码
    const codeEl = document.getElementById('agent-invite-code');
    const linkEl = document.getElementById('agent-invite-link');
    if (codeEl) codeEl.textContent = agent.invite_code || '--';
    if (linkEl) {
      const link = window.location.origin + '/dashboard?ref=' + (agent.invite_code || '');
      linkEl.textContent = link;
    }

    // 显示已绑定的默认收款码
    renderBoundQrcode(agent.default_qrcode_path);

    // 加载佣金明细
    await loadAgentCommissions();
    // 加载提现记录
    await loadWithdrawalHistory();
  }
}

async function loadAgentCommissions() {
  try {
    const records = await api('/api/user/agent/commissions');
    const body = document.getElementById('agent-commissions-body');
    if (!body) return;
    const sourceLabel = { recharge: '充值分成' };
    body.innerHTML = records.length
      ? records.map(r => {
          return '<tr>' +
            '<td>' + fmtTime(r.created_at) + '</td>' +
            '<td style="color:#22c55e">+' + fmtMoney(r.commission_amount) + '</td>' +
            '<td>' + (sourceLabel[r.source] || r.source) + '</td>' +
            '<td>' + (r.remark || '-') + '</td>' +
            '</tr>';
        }).join('')
      : '<tr><td colspan="4" style="color:var(--muted)">暂无佣金记录，分享邀请码后将在此显示</td></tr>';
  } catch (e) {
    const body = document.getElementById('agent-commissions-body');
    if (body) body.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">加载失败</td></tr>';
  }
}

async function applyAgent() {
  const remark = document.getElementById('agent-apply-remark').value.trim();
  const msg = document.getElementById('agent-apply-msg');
  msg.textContent = '';
  msg.style.color = 'var(--danger)';
  try {
    await api('/api/user/agent/apply', { method: 'POST', body: JSON.stringify({ remark: remark || null }) });
    msg.style.color = 'var(--success)';
    msg.textContent = '申请已提交！请等待管理员审批';
    await loadAgentInfo();
  } catch (err) {
    msg.textContent = err.message;
  }
}

// 选择提现收款方式
let _wdPayMethod = 'wechat';
let _wdQrcodePath = '';  // 已上传的收款码路径

function selectWdPay(method) {
  _wdPayMethod = method;
  const wBtn = document.getElementById('wd-pay-wechat');
  const aBtn = document.getElementById('wd-pay-alipay');
  if (wBtn) wBtn.style.background = method === 'wechat' ? 'var(--primary)' : '';
  if (wBtn) wBtn.style.color = method === 'wechat' ? '#fff' : '';
  if (aBtn) aBtn.style.background = method === 'alipay' ? 'var(--primary)' : '';
  if (aBtn) aBtn.style.color = method === 'alipay' ? '#fff' : '';
}

async function handleQrcodeUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  const msg = document.getElementById('qrcode-msg');
  const placeholder = document.getElementById('qrcode-placeholder');
  const preview = document.getElementById('qrcode-preview');
  msg.textContent = '上传中...';
  msg.style.color = 'var(--muted)';

  try {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch('/api/user/agent/upload-qrcode', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getToken() },
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || '上传失败');
    }
    const result = await resp.json();
    _wdQrcodePath = result.url;
    if (placeholder) placeholder.style.display = 'none';
    if (preview) {
      preview.src = result.url;
      preview.style.display = 'block';
    }
    msg.textContent = '✅ 收款码已上传';
    msg.style.color = '#22c55e';
  } catch (e) {
    msg.textContent = '❌ ' + e.message;
    msg.style.color = 'var(--danger)';
    _wdQrcodePath = '';
  }
}

// ============================================================
//  绑定默认收款码
// ============================================================
let _bindQrcodeTempPath = '';  // 上传但未确认绑定的临时路径

function renderBoundQrcode(defaultQrcodePath) {
  const display = document.getElementById('bound-qrcode-display');
  const upload = document.getElementById('bind-qrcode-upload');
  if (!display || !upload) return;

  if (defaultQrcodePath) {
    display.style.display = 'block';
    upload.style.display = 'none';
    const img = document.getElementById('bound-qrcode-img');
    if (img) img.src = defaultQrcodePath;
    // 也设置到提现区域，让提现时可以读取
    window._boundQrcodePath = defaultQrcodePath;
  } else {
    display.style.display = 'none';
    upload.style.display = 'block';
    window._boundQrcodePath = '';
  }
}

function startRebindQrcode() {
  // 显示上传区域，允许重新上传
  const upload = document.getElementById('bind-qrcode-upload');
  if (upload) upload.style.display = 'block';
  _bindQrcodeTempPath = '';
  const preview = document.getElementById('bind-qrcode-preview');
  const placeholder = document.getElementById('bind-qrcode-placeholder');
  const confirmBtn = document.getElementById('bind-qrcode-confirm-btn');
  const msg = document.getElementById('bind-qrcode-msg');
  if (preview) { preview.src = ''; preview.style.display = 'none'; }
  if (placeholder) placeholder.style.display = '';
  if (confirmBtn) confirmBtn.style.display = 'none';
  if (msg) { msg.textContent = ''; msg.style.color = 'var(--muted)'; }
  // 清空 file input
  const fileInput = document.getElementById('bind-qrcode-file-input');
  if (fileInput) fileInput.value = '';
}

async function handleBindQrcodeUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  const msg = document.getElementById('bind-qrcode-msg');
  const placeholder = document.getElementById('bind-qrcode-placeholder');
  const preview = document.getElementById('bind-qrcode-preview');
  const confirmBtn = document.getElementById('bind-qrcode-confirm-btn');
  msg.textContent = '上传中...';
  msg.style.color = 'var(--muted)';

  try {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch('/api/user/agent/upload-qrcode', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + getToken() },
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || '上传失败');
    }
    const result = await resp.json();
    _bindQrcodeTempPath = result.url;
    if (placeholder) placeholder.style.display = 'none';
    if (preview) {
      preview.src = result.url;
      preview.style.display = 'block';
    }
    if (confirmBtn) confirmBtn.style.display = 'block';
    msg.textContent = '✅ 上传成功，点击下方按钮确认绑定';
    msg.style.color = '#22c55e';
  } catch (e) {
    msg.textContent = '❌ ' + e.message;
    msg.style.color = 'var(--danger)';
    _bindQrcodeTempPath = '';
  }
}

async function confirmBindQrcode() {
  if (!_bindQrcodeTempPath) {
    alert('请先上传收款码');
    return;
  }
  const msg = document.getElementById('bind-qrcode-msg');
  try {
    await api('/api/user/agent/bind-qrcode', {
      method: 'POST',
      body: JSON.stringify({ qrcode_path: _bindQrcodeTempPath }),
    });
    _bindQrcodeTempPath = '';
    msg.textContent = '✅ 收款码绑定成功！';
    msg.style.color = '#22c55e';
    // 重新加载代理信息以显示绑定状态
    await loadAgentInfo();
  } catch (err) {
    msg.textContent = '❌ ' + err.message;
    msg.style.color = 'var(--danger)';
  }
}

// ============================================================
//  提现确认弹窗（一键绑定收款码流程）
// ============================================================
let _wdPendingAmount = 0;       // 暂存提现金额
let _wdPendingPayMethod = 'wechat';  // 暂存收款方式
let _wdUseNewQrcode = false;    // 是否选择重新上传

function showWithdrawConfirmModal(amount, payMethod, qrcodePath) {
  _wdPendingAmount = amount;
  _wdPendingPayMethod = payMethod;
  _wdUseNewQrcode = false;

  document.getElementById('wd-confirm-amount').textContent = '¥' + amount.toFixed(2);
  document.getElementById('wd-confirm-method').textContent = payMethod === 'wechat' ? '微信' : '支付宝';
  const img = document.getElementById('wd-confirm-qrcode-img');
  if (img) img.src = qrcodePath;
  document.getElementById('withdraw-confirm-modal').style.display = 'flex';
}

function closeWithdrawConfirmModal() {
  document.getElementById('withdraw-confirm-modal').style.display = 'none';
  _wdPendingAmount = 0;
  _wdUseNewQrcode = false;
}

async function confirmWithdrawWithBound() {
  // 先保存值再关闭弹窗（closeWithdrawConfirmModal 会重置 _wdPendingAmount 为 0）
  const amount = _wdPendingAmount;
  const method = _wdPendingPayMethod;
  const qrcode = window._boundQrcodePath;
  closeWithdrawConfirmModal();
  // 使用已绑定的收款码发起提现
  await doWithdraw(amount, method, qrcode);
}

function startNewQrcodeUpload() {
  // 关闭确认弹窗，让用户在提现区域重新上传
  closeWithdrawConfirmModal();
  _wdUseNewQrcode = true;
  // 显示上传区域并重置
  _wdQrcodePath = '';
  const section = document.getElementById('qrcode-upload-section');
  if (section) section.style.display = 'block';
  const placeholder = document.getElementById('qrcode-placeholder');
  const preview = document.getElementById('qrcode-preview');
  const qrcodeMsg = document.getElementById('qrcode-msg');
  const fileInput = document.getElementById('qrcode-file-input');
  if (placeholder) placeholder.style.display = '';
  if (preview) { preview.src = ''; preview.style.display = 'none'; }
  if (qrcodeMsg) { qrcodeMsg.textContent = '请上传新的收款码'; qrcodeMsg.style.color = 'var(--warning,#f59e0b)'; }
  if (fileInput) fileInput.value = '';
  // 滚动到收款码上传区域
  const uploadArea = document.getElementById('qrcode-upload-area');
  if (uploadArea) uploadArea.scrollIntoView({ behavior: 'smooth' });
}

async function doWithdraw(amount, payMethod, qrcodePath) {
  const msg = document.getElementById('withdraw-msg');
  msg.textContent = '';
  msg.style.color = 'var(--danger)';
  if (!amount || amount <= 0) { msg.textContent = '请输入正确的提现金额'; return; }
  if (!qrcodePath) { msg.textContent = '请先上传收款码'; return; }
  try {
    const result = await api('/api/user/agent/withdraw', {
      method: 'POST',
      body: JSON.stringify({ amount, pay_method: payMethod, qrcode_path: qrcodePath }),
    });
    msg.style.color = 'var(--success)';
    msg.textContent = result.message || '提现申请已提交！约 1 小时内到账。';
    document.getElementById('withdraw-amount').value = '';
    // 重置收款码（如果使用的是临时上传的收款码）
    if (_wdUseNewQrcode || !window._boundQrcodePath) {
      _wdQrcodePath = '';
      const section = document.getElementById('qrcode-upload-section');
      const placeholder = document.getElementById('qrcode-placeholder');
      const preview = document.getElementById('qrcode-preview');
      const qrcodeMsg = document.getElementById('qrcode-msg');
      const fileInput = document.getElementById('qrcode-file-input');
      if (section) section.style.display = 'none';  // 重新隐藏上传区域
      if (placeholder) placeholder.style.display = '';
      if (preview) { preview.src = ''; preview.style.display = 'none'; }
      if (qrcodeMsg) { qrcodeMsg.textContent = '未上传收款码'; qrcodeMsg.style.color = 'var(--muted)'; }
      if (fileInput) fileInput.value = '';
    }
    await loadAgentInfo();
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function agentWithdraw() {
  const amount = parseFloat(document.getElementById('withdraw-amount').value);
  const msg = document.getElementById('withdraw-msg');
  msg.textContent = '';
  msg.style.color = 'var(--danger)';
  if (!amount || amount <= 0) { msg.textContent = '请输入正确的提现金额'; return; }

  // 如果有已绑定的收款码且用户没有选择重新上传，弹出确认弹窗
  if (window._boundQrcodePath && !_wdUseNewQrcode) {
    showWithdrawConfirmModal(amount, _wdPayMethod, window._boundQrcodePath);
    return;
  }

  // 没有绑定收款码或选择了重新上传，需要先上传
  if (!_wdQrcodePath) {
    // 显示上传区域
    const section = document.getElementById('qrcode-upload-section');
    if (section) {
      section.style.display = 'block';
      msg.style.color = 'var(--warning,#f59e0b)';
      msg.textContent = '⚠️ 请先上传收款码后再提交提现';
      document.getElementById('qrcode-upload-area').scrollIntoView({ behavior: 'smooth' });
    } else {
      msg.textContent = '请先上传收款码';
    }
    return;
  }
  await doWithdraw(amount, _wdPayMethod, _wdQrcodePath);
}

async function withdrawAll() {
  try {
    const agent = await api('/api/user/agent/info');
    const avail = agent.available_commission;
    if (!avail || avail <= 0) {
      const msg = document.getElementById('withdraw-msg');
      msg.style.color = 'var(--muted)';
      msg.textContent = '可用佣金余额为 0，无法提现';
      return;
    }
    document.getElementById('withdraw-amount').value = avail.toFixed(2);
  } catch (err) {
    const msg = document.getElementById('withdraw-msg');
    if (msg) { msg.style.color = 'var(--danger)'; msg.textContent = err.message; }
  }
}

async function loadWithdrawalHistory() {
  const body = document.getElementById('withdrawal-history-body');
  if (!body) return;
  try {
    const records = await api('/api/user/agent/withdrawals');
    const statusColor = { '待处理': 'var(--warning,#f59e0b)', '已到账': '#22c55e', '已拒绝': 'var(--danger)' };
    body.innerHTML = records.length
      ? records.map(r => {
          return '<tr>' +
          '<td>' + fmtTime(r.created_at) + '</td>' +
          '<td>' + fmtMoney(r.amount) + '</td>' +
          '<td>' + r.pay_method + '</td>' +
          '<td style="color:' + (statusColor[r.status] || '') + '">' + r.status + '</td>' +
          '<td>' + (r.remark || (r.status === '待处理' ? '⏳ 管理员处理中' : '-')) + '</td>' +
          '</tr>';
        }).join('')
      : '<tr><td colspan="5" style="color:var(--muted)">暂无提现记录</td></tr>';
  } catch (e) {
    body.innerHTML = '<tr><td colspan="5" style="color:var(--muted)">加载失败</td></tr>';
  }
}

// 收款码大图弹窗
function showQrModal(url) {
  let modal = document.getElementById('qr-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'qr-modal';
    modal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,.75);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer';
    modal.onclick = function() { modal.style.display = 'none'; };
    document.body.appendChild(modal);
  }
  modal.innerHTML = '<img src="' + url + '" style="max-width:80vw;max-height:80vh;border-radius:10px;box-shadow:0 4px 30px rgba(0,0,0,.5)" />';
  modal.style.display = 'flex';
}

// ============================================================
//  管理端 - 代理管理
// ============================================================

async function loadAgents() {
  const body = document.getElementById('agents-body');
  if (!body) return;

  try {
    const agents = await api('/api/admin/agents');
    const statusLabel = { pending: '待审批', approved: '已通过', rejected: '已拒绝', disabled: '已禁用' };
    const statusColor = { pending: 'var(--warning,#f59e0b)', approved: '#22c55e', rejected: 'var(--danger)', disabled: 'var(--muted)' };

    const total = agents.length;
    const pending = agents.filter(a => a.status === 'pending').length;
    const active = agents.filter(a => a.status === 'approved').length;
    const totalComm = agents.reduce((s, a) => s + a.total_commission, 0);

    const tc = document.getElementById('agent-total-count');
    const pc = document.getElementById('agent-pending-count');
    const ac = document.getElementById('agent-active-count');
    const tcomm = document.getElementById('agent-total-commission');
    if (tc) tc.textContent = total;
    if (pc) pc.textContent = pending;
    if (ac) ac.textContent = active;
    if (tcomm) tcomm.textContent = fmtMoney(totalComm);

    body.innerHTML = agents.length
      ? agents.map(a => {
          const btns = [];
          if (a.status === 'pending') {
            btns.push('<button class="btn btn-primary btn-sm" onclick="approveAgent(' + a.id + ')">通过</button>');
            btns.push('<button class="btn btn-outline btn-sm" onclick="rejectAgent(' + a.id + ')" style="color:var(--danger)">拒绝</button>');
          } else if (a.status === 'approved') {
            btns.push('<button class="btn btn-outline btn-sm" onclick="toggleAgentStatus(' + a.id + ')" style="color:var(--danger)">禁用</button>');
            btns.push('<button class="btn btn-outline btn-sm" onclick="viewAgentDetail(' + a.id + ', \'' + escapeAttr(a.username) + '\')">明细</button>');
          } else if (a.status === 'disabled') {
            btns.push('<button class="btn btn-primary btn-sm" onclick="toggleAgentStatus(' + a.id + ')">恢复</button>');
            btns.push('<button class="btn btn-outline btn-sm" onclick="viewAgentDetail(' + a.id + ', \'' + escapeAttr(a.username) + '\')">明细</button>');
          }
          return '<tr>' +
            '<td>' + a.id + '</td>' +
            '<td>' + escapeAttr(a.username) + '</td>' +
            '<td><code>' + (a.invite_code || '-') + '</code></td>' +
            '<td style="color:' + (statusColor[a.status] || '') + '">' + (statusLabel[a.status] || a.status) + '</td>' +
            '<td>' + (a.commission_rate * 100).toFixed(0) + '%</td>' +
            '<td>' + fmtMoney(a.total_commission) + '</td>' +
            '<td style="color:#22c55e">' + fmtMoney(a.available_commission) + '</td>' +
            '<td>' + fmtTime(a.applied_at) + '</td>' +
            '<td style="display:flex;gap:4px;flex-wrap:wrap">' + btns.join(' ') + '</td>' +
            '</tr>';
        }).join('')
      : '<tr><td colspan="9" style="color:var(--muted)">暂无代理申请</td></tr>';
  } catch (e) {
    body.innerHTML = '<tr><td colspan="9" style="color:var(--muted)">加载失败：' + e.message + '</td></tr>';
  }
}

async function approveAgent(id) {
  if (!confirm('确认审批通过该代理？')) return;
  try {
    const r = await api('/api/admin/agents/' + id + '/approve', { method: 'POST' });
    alert('审批通过！代理邀请码：' + r.invite_code);
    await loadAgents();
  } catch (err) {
    alert('操作失败：' + err.message);
  }
}

async function rejectAgent(id) {
  if (!confirm('确认拒绝该代理申请？')) return;
  try {
    await api('/api/admin/agents/' + id + '/reject', { method: 'POST' });
    await loadAgents();
  } catch (err) {
    alert('操作失败：' + err.message);
  }
}

async function toggleAgentStatus(id) {
  try {
    const r = await api('/api/admin/agents/' + id + '/disable', { method: 'POST' });
    await loadAgents();
  } catch (err) {
    alert('操作失败：' + err.message);
  }
}

async function viewAgentDetail(id, username) {
  const panel = document.getElementById('agent-detail-panel');
  const title = document.getElementById('agent-detail-title');
  const body = document.getElementById('agent-detail-body');
  if (!panel || !body) return;
  if (title) title.textContent = '代理佣金明细 — ' + username + ' (ID:' + id + ')';
  panel.style.display = 'block';
  body.innerHTML = '<tr><td colspan="7" style="color:var(--muted)">加载中...</td></tr>';
  panel.scrollIntoView({ behavior: 'smooth' });
  try {
    const records = await api('/api/admin/agents/' + id + '/commissions');
    const sourceLabel = { recharge: '充值分成', withdraw: '提现' };
    body.innerHTML = records.length
      ? records.map(r =>
          '<tr>' +
          '<td>' + fmtTime(r.created_at) + '</td>' +
          '<td>UID ' + r.user_id + '</td>' +
          '<td>' + (r.recharge_amount > 0 ? fmtMoney(r.recharge_amount) : '-') + '</td>' +
          '<td style="color:' + (r.commission_amount >= 0 ? '#22c55e' : 'var(--danger)') + '">' +
            (r.commission_amount >= 0 ? '+' : '') + fmtMoney(r.commission_amount) + '</td>' +
          '<td>' + (r.platform_amount > 0 ? fmtMoney(r.platform_amount) : '-') + '</td>' +
          '<td>' + (sourceLabel[r.source] || r.source) + '</td>' +
          '<td>' + (r.remark || '-') + '</td>' +
          '</tr>'
        ).join('')
      : '<tr><td colspan="7" style="color:var(--muted)">暂无佣金记录</td></tr>';
  } catch (e) {
    body.innerHTML = '<tr><td colspan="7" style="color:var(--muted)">加载失败</td></tr>';
  }
}

function closeAgentDetail() {
  const panel = document.getElementById('agent-detail-panel');
  if (panel) panel.style.display = 'none';
}

// ============================================================
//  管理端 - 提现申请管理
// ============================================================

async function loadWithdrawals() {
  const body = document.getElementById('withdrawals-body');
  if (!body) return;
  try {
    const list = await api('/api/admin/agent-withdrawals');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="8" style="color:var(--muted)">暂无提现申请</td></tr>';
      return;
    }
    body.innerHTML = list.map(w => {
      const btns = [];
      if (w.status_raw === 'pending') {
        btns.push('<button class="btn btn-primary btn-sm" onclick="completeWithdrawal(' + w.id + ')">✅ 已打款</button>');
        btns.push('<button class="btn btn-outline btn-sm" onclick="rejectWithdrawal(' + w.id + ')" style="color:var(--danger)">拒绝</button>');
      }
      const qrHtml = w.qrcode_path
        ? '<img src="' + escapeAttr(w.qrcode_path) + '" style="max-width:60px;max-height:60px;border-radius:4px;cursor:pointer" onclick="showQrModal(\'' + escapeAttr(w.qrcode_path) + '\')" title="点击查看大图" />'
        : (w.pay_account ? '<span style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block" title="' + escapeAttr(w.pay_account) + '">' + escapeAttr(w.pay_account) + '</span>' : '-');
      return '<tr>' +
        '<td>' + w.id + '</td>' +
        '<td>' + escapeAttr(w.username) + '</td>' +
        '<td style="color:#22c55e;font-weight:600">' + fmtMoney(w.amount) + '</td>' +
        '<td>' + w.pay_method + '</td>' +
        '<td>' + qrHtml + '</td>' +
        '<td style="color:' + w.status_color + '">' + w.status + '</td>' +
        '<td>' + fmtTime(w.created_at) + '</td>' +
        '<td style="display:flex;gap:4px;flex-wrap:wrap">' + btns.join(' ') + '</td>' +
        '</tr>';
    }).join('');
  } catch (e) {
    body.innerHTML = '<tr><td colspan="8" style="color:var(--muted)">加载失败：' + e.message + '</td></tr>';
  }
}

async function completeWithdrawal(id) {
  if (!confirm('确认已向该代理打款完成？此操作不可撤销。')) return;
  try {
    await api('/api/admin/agent-withdrawals/' + id + '/complete', { method: 'POST' });
    await loadWithdrawals();
  } catch (err) {
    alert('操作失败：' + err.message);
  }
}

async function rejectWithdrawal(id) {
  if (!confirm('确认拒绝该提现申请？拒绝后佣金将退回代理账户。')) return;
  try {
    await api('/api/admin/agent-withdrawals/' + id + '/reject', { method: 'POST' });
    await loadWithdrawals();
    await loadAgents(); // 刷新代理列表（可用佣金已退回）
  } catch (err) {
    alert('操作失败：' + err.message);
  }
}
<<<<<<< HEAD

// ============================================================
//  管理端 - 降级映射管理
// ============================================================

async function loadFallbacks() {
  const list = document.getElementById('fallbacks-list');
  if (!list) return;
  try {
    const fallbacks = await api('/api/admin/fallbacks');
    window._adminFallbacks = {};
    fallbacks.forEach(f => { window._adminFallbacks[f.id] = f; });
    list.innerHTML = fallbacks.length
      ? fallbacks.map(f =>
        '<div class="channel-item">' +
          '<strong>' + escapeAttr(f.source_model) + '</strong> → <strong>' + escapeAttr(f.target_model) + '</strong>' +
          ' · 优先级: ' + f.priority +
          ' · ' + (f.is_active ? '<span style="color:#22c55e">启用</span>' : '<span style="color:var(--muted)">禁用</span>') +
          ' <button class="btn btn-outline btn-sm" onclick="editFallbackForm(' + f.id + ', window._adminFallbacks[' + f.id + '])">编辑</button>' +
          ' <button class="btn btn-outline btn-sm" onclick="deleteFallback(' + f.id + ')" style="color:var(--danger)">删除</button>' +
        '</div>'
      ).join('')
      : '<p class="muted-text">暂无降级映射，请点击「添加映射」创建</p>';
  } catch (e) {
    list.innerHTML = '<p class="muted-text">降级映射加载失败</p>';
  }
}

function showFallbackForm() {
  document.getElementById('modal-title').textContent = '添加降级映射';
  document.getElementById('modal-body').innerHTML =
    '<label>源模型</label><input id="fb-source" placeholder="例如：gpt-4o" autofocus>' +
    '<label>目标模型</label><input id="fb-target" placeholder="例如：gpt-4o-mini">' +
    '<label>优先级（数字越小越优先）</label><input id="fb-priority" type="number" value="0" min="0" max="99">' +
    '<label style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="fb-active" checked> 启用</label>';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '确认添加';
  document.getElementById('modal-submit').onclick = async () => {
    const source = document.getElementById('fb-source').value.trim();
    const target = document.getElementById('fb-target').value.trim();
    if (!source || !target) { alert('请填写源模型和目标模型'); return; }
    if (source === target) { alert('源模型和目标模型不能相同'); return; }
    try {
      await api('/api/admin/fallbacks', { method: 'POST', body: JSON.stringify({
        source_model: source,
        target_model: target,
        priority: parseInt(document.getElementById('fb-priority').value, 10) || 0,
        is_active: document.getElementById('fb-active').checked,
      })});
      closeModal();
      await loadFallbacks();
    } catch (err) { alert(err.message); }
  };
}

function editFallbackForm(id, current) {
  document.getElementById('modal-title').textContent = '编辑降级映射';
  document.getElementById('modal-body').innerHTML =
    '<label>源模型</label><input id="fb-source" value="' + escapeAttr(current.source_model) + '">' +
    '<label>目标模型</label><input id="fb-target" value="' + escapeAttr(current.target_model) + '">' +
    '<label>优先级（数字越小越优先）</label><input id="fb-priority" type="number" value="' + current.priority + '" min="0" max="99">' +
    '<label style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="fb-active"' + (current.is_active ? ' checked' : '') + '> 启用</label>';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '保存修改';
  document.getElementById('modal-submit').onclick = async () => {
    const source = document.getElementById('fb-source').value.trim();
    const target = document.getElementById('fb-target').value.trim();
    if (!source || !target) { alert('请填写源模型和目标模型'); return; }
    try {
      await api('/api/admin/fallbacks/' + id, { method: 'PUT', body: JSON.stringify({
        source_model: source,
        target_model: target,
        priority: parseInt(document.getElementById('fb-priority').value, 10) || 0,
        is_active: document.getElementById('fb-active').checked,
      })});
      closeModal();
      await loadFallbacks();
    } catch (err) { alert(err.message); }
  };
}

async function deleteFallback(id) {
  if (!confirm('确认删除该降级映射？')) return;
  try {
    await api('/api/admin/fallbacks/' + id, { method: 'DELETE' });
    await loadFallbacks();
  } catch (err) { alert('删除失败：' + err.message); }
}

// ============================================================
//  管理端 - 毛利报告
// ============================================================

async function loadMarginReport() {
  const body = document.getElementById('margin-body');
  if (!body) return;
  try {
    const report = await api('/api/admin/pricing/margin');

    // 总览卡片
    const revEl = document.getElementById('margin-total-revenue');
    const costEl = document.getElementById('margin-total-cost');
    const profitEl = document.getElementById('margin-total-profit');
    const pctEl = document.getElementById('margin-overall-pct');
    if (revEl) revEl.textContent = fmtMoney(report.summary.total_revenue);
    if (costEl) costEl.textContent = fmtMoney(report.summary.total_cost);
    if (profitEl) profitEl.textContent = fmtMoney(report.summary.total_profit);
    if (pctEl) pctEl.textContent = report.summary.overall_margin_pct + '%';

    // 模型明细表
    body.innerHTML = report.items.length
      ? report.items.map(item =>
        '<tr>' +
          '<td><code>' + escapeAttr(item.model) + '</code></td>' +
          '<td>' + fmtMoney(item.cost_price) + '</td>' +
          '<td>' + fmtMoney(item.selling_price) + '</td>' +
          '<td>' + fmtMoney(item.input_price) + '</td>' +
          '<td>' + fmtMoney(item.output_price) + '</td>' +
          '<td style="color:' + (item.profit >= 0 ? '#22c55e' : 'var(--danger)') + '">' + fmtMoney(item.profit) + '</td>' +
          '<td style="color:' + (item.margin_pct >= 0 ? '#22c55e' : 'var(--danger)') + '">' + item.margin_pct + '%</td>' +
          '<td>' + item.usage_count + '</td>' +
          '<td style="color:#22c55e">' + fmtMoney(item.revenue) + '</td>' +
          '<td style="color:' + (item.profit_total >= 0 ? 'var(--primary)' : 'var(--danger)') + '">' + fmtMoney(item.profit_total) + '</td>' +
        '</tr>'
      ).join('')
      : '<tr><td colspan="10" style="color:var(--muted)">暂无毛利数据，请先在「定价管理」中为模型设置成本价格</td></tr>';
  } catch (e) {
    body.innerHTML = '<tr><td colspan="10" style="color:var(--muted)">加载失败：' + e.message + '</td></tr>';
  }
}
=======
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
