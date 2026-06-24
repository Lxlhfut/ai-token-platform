const API = '';

function getToken() { return localStorage.getItem('token'); }
function setToken(t) { localStorage.setItem('token', t); }
function clearToken() { localStorage.removeItem('token'); }

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

function initUserDashboard() {
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
    try {
      await api('/api/user/register', {
        method: 'POST',
        body: JSON.stringify({
          username: fd.get('username'),
          password: password,
          agreed_terms: true,
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

  document.getElementById('logout-btn').onclick = () => { clearToken(); location.reload(); };
  document.getElementById('create-key-btn').onclick = async () => {
    try {
      await api('/api/user/api-keys', { method: 'POST', body: JSON.stringify({ name: 'key-' + Date.now() }) });
      await loadUserPanel();
    } catch (err) { alert(err.message); }
  };

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

  // 扫码支付：选择支付方式
  window._selectedPayMethod = 'wechat';
  window._currentOrderNo = null;

  // 生成支付二维码
  document.getElementById('create-order-btn').onclick = async () => {
    const amount = parseFloat(document.getElementById('scan-amount').value);
    const msg = document.getElementById('redeem-msg');
    msg.textContent = '';
    msg.style.color = 'var(--danger)';
    if (!amount || amount < 0.01) { msg.textContent = '请输入正确的充值金额（最低 0.01 元）'; return; }
    try {
      const order = await api('/api/user/recharge-order', {
        method: 'POST',
        body: JSON.stringify({ amount, pay_method: window._selectedPayMethod }),
      });
      window._currentOrderNo = order.order_no;
      document.getElementById('payment-info').textContent =
        '请使用 ' + (window._selectedPayMethod === 'wechat' ? '微信' : '支付宝') + ' 扫描支付';
      document.getElementById('qr-amount-display').textContent = '¥' + amount.toFixed(2);
      document.getElementById('qr-order-no').textContent = '订单号：' + order.order_no;
      document.getElementById('payment-modal').style.display = 'flex';
    } catch (err) {
      msg.textContent = err.message;
    }
  };

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
    const firstKey = keys.length ? keys[0].key : '（请先创建 API Key）';
    const baseUrl = window.location.origin + '/v1';

    // 接入配置卡片（概览 + API Key 两个标签页）
    const baseUrlEls = ['display-base-url', 'display-base-url-2'];
    const apiKeyEls = ['display-api-key', 'display-api-key-2'];
    baseUrlEls.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = baseUrl; });
    apiKeyEls.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = firstKey; });

    document.getElementById('keys-list').innerHTML = keys.length
      ? keys.map(k => '<div class="key-item"><div><span class="key-name">' + k.name + '</span><code class="key-value">' + k.key + '</code></div><button class="btn btn-outline btn-sm" data-key="' + k.key + '" onclick="copyText(this.dataset.key, this)">复制</button></div>').join('')
      : '<p class="muted-text">暂无 Key，请点击创建新 Key</p>';

    // Python 代码示例
    const codeEl = document.getElementById('code-example');
    if (codeEl) {
      updateCodeExample(firstKey, baseUrl);
    }

    document.getElementById('pricing-body').innerHTML = pricing.length
      ? pricing.map(p => '<tr><td><code>' + p.model + '</code></td><td>' + p.input_price + '</td><td>' + p.output_price + '</td><td>' + (p.description || '-') + '</td></tr>').join('')
      : '<tr><td colspan="4">暂无定价信息</td></tr>';

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
      const statusLabel = { pending: '待支付', paid: '已支付', cancelled: '已取消' };
      const payLabel = { wechat: '微信', alipay: '支付宝' };
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
  document.getElementById('admin-logout').onclick = () => { clearToken(); location.reload(); };
  if (getToken()) loadAdminPanel().catch(() => clearToken());
}

async function loadAdminPanel() {
  const stats = await api('/api/admin/stats');
  document.getElementById('admin-login').style.display = 'none';
  document.getElementById('app-layout').style.display = 'flex';
  document.getElementById('admin-logout').style.display = 'inline-flex';
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
      ? pricing.map(p =>
        '<div class="pricing-item"><strong>' + p.model + '</strong><br>输入: ' + p.input_price + '/1K · 输出: ' + p.output_price + '/1K' +
        ' <button class="btn btn-outline btn-sm" onclick="editPricingForm(' + p.id + ', window._adminPricing[' + p.id + '])" style="margin-top:4px">编辑</button>' +
        ' <button class="btn btn-outline btn-sm" onclick="deletePricing(' + p.id + ')" style="margin-top:4px;color:var(--danger)">删除</button></div>'
      ).join('')
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
    const statusLabel = { pending: '待支付', paid: '已支付', cancelled: '已取消' };
    const payLabel = { wechat: '微信支付', alipay: '支付宝' };
    document.getElementById('orders-body').innerHTML = orders.length
      ? orders.map(o =>
          '<tr>' +
          '<td><code style="font-size:.75rem">' + o.order_no + '</code></td>' +
          '<td>' + o.user_id + '</td>' +
          '<td>' + fmtMoney(o.amount) + '</td>' +
          '<td>' + (payLabel[o.pay_method] || o.pay_method) + '</td>' +
          '<td>' + (statusLabel[o.status] || o.status) + '</td>' +
          '<td>' + fmtTime(o.created_at) + '</td>' +
          '</tr>'
        ).join('')
      : '<tr><td colspan="6" style="color:var(--muted)">暂无充值订单</td></tr>';
  } catch (e) {
    document.getElementById('orders-body').innerHTML = '<tr><td colspan="6" style="color:var(--muted)">加载失败</td></tr>';
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

function showPricingForm() {
  document.getElementById('modal-title').textContent = '\u6dfb\u52a0\u6a21\u578b\u5b9a\u4ef7';
  document.getElementById('modal-body').innerHTML =
    '<label>\u6a21\u578b\u540d</label><input id="pr-model" placeholder="gpt-4o-mini">' +
    '<label>\u8f93\u5165\u4ef7\u683c\uff08\u5143/1K tokens\uff09</label><input id="pr-in" type="number" step="0.0001" value="0.001">' +
    '<label>\u8f93\u51fa\u4ef7\u683c\uff08\u5143/1K tokens\uff09</label><input id="pr-out" type="number" step="0.0001" value="0.004">';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '\u786e\u8ba4';
  document.getElementById('modal-submit').onclick = async () => {
    try {
      await api('/api/admin/pricing', { method: 'POST', body: JSON.stringify({
        model: document.getElementById('pr-model').value,
        input_price: parseFloat(document.getElementById('pr-in').value),
        output_price: parseFloat(document.getElementById('pr-out').value),
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
    '<label>输入价格（元/1K tokens）</label><input id="pr-in" type="number" step="0.0001" value="' + current.input_price + '">' +
    '<label>输出价格（元/1K tokens）</label><input id="pr-out" type="number" step="0.0001" value="' + current.output_price + '">' +
    '<label>说明</label><input id="pr-desc" value="' + escapeAttr(current.description || '') + '">';
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modal-submit').textContent = '保存修改';
  document.getElementById('modal-submit').onclick = async () => {
    try {
      await api('/api/admin/pricing/' + id, { method: 'PUT', body: JSON.stringify({
        model: document.getElementById('pr-model').value,
        input_price: parseFloat(document.getElementById('pr-in').value),
        output_price: parseFloat(document.getElementById('pr-out').value),
        description: document.getElementById('pr-desc').value.trim() || null,
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

// ======= 快捷金额 =======
function setScanAmount(amount) {
  document.getElementById('scan-amount').value = amount;
}

// ======= 关闭支付弹窗 =======
function closePaymentModal() {
  document.getElementById('payment-modal').style.display = 'none';
  window._currentOrderNo = null;
}

// ======= 确认支付 =======
async function confirmPayment() {
  if (!window._currentOrderNo) {
    alert('未找到订单信息，请重新生成');
    return;
  }
  const btn = document.getElementById('confirm-pay-btn');
  const payMsg = document.getElementById('pay-error-msg');
  if (payMsg) { payMsg.textContent = ''; payMsg.style.color = 'var(--danger)'; }
  if (btn) { btn.disabled = true; btn.textContent = '处理中...'; }
  try {
    const result = await api('/api/user/recharge-order/' + window._currentOrderNo + '/confirm', {
      method: 'POST',
    });
    document.getElementById('payment-modal').style.display = 'none';
    window._currentOrderNo = null;
    const msg = document.getElementById('redeem-msg');
    msg.style.color = 'var(--success)';
    msg.textContent = '充值成功！到账 ' + fmtMoney(result.amount) + '，当前余额：' + fmtMoney(result.balance);
    await loadUserPanel();
  } catch (err) {
    if (payMsg) { payMsg.textContent = err.message; }
    else { alert(err.message); }
    if (btn) { btn.disabled = false; btn.textContent = '✅ 我已支付完成'; }
  }
}
