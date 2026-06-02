// 法律网站前端交互
document.addEventListener('DOMContentLoaded', function() {
    // 移动端菜单
    document.addEventListener('click', function(e) {
        var menu = document.getElementById('mobileMenu');
        var btn = document.querySelector('.mobile-menu-btn');
        if (menu && menu.classList.contains('active')) {
            if (!menu.contains(e.target) && !btn.contains(e.target)) {
                menu.classList.remove('active');
            }
        }
    });

    // 导航高亮
    var currentPath = window.location.pathname;
    document.querySelectorAll('.main-nav a').forEach(function(link) {
        if (link.getAttribute('href') === currentPath) {
            link.style.color = 'var(--accent)';
        }
    });

    // =======================
    // 证书展示：点击缩略图 → 更新大图
    // =======================
    document.querySelectorAll('.cert-showcase').forEach(function(showcase) {
        var featured = showcase.querySelector('.cert-featured .featured-info');
        var strip = showcase.querySelector('.strip-track');
        if (!featured || !strip) return;

        var titleEl = featured.querySelector('h3');
        var issuerEl = featured.querySelector('.featured-issuer');
        var dateEl = featured.querySelector('.featured-date');
        var descEl = featured.querySelector('.featured-desc');

        var cards = strip.querySelectorAll('.strip-card');

        cards.forEach(function(card) {
            card.addEventListener('click', function() {
                cards.forEach(function(c) { c.classList.remove('active'); });
                this.classList.add('active');
                this.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
                if (titleEl) titleEl.textContent = this.getAttribute('data-title') || '';
                if (issuerEl) issuerEl.textContent = this.getAttribute('data-issuer') || '';
                if (dateEl) dateEl.textContent = this.getAttribute('data-date') || '';
                if (descEl) descEl.textContent = this.getAttribute('data-desc') || '';
            });
        });

        var prevBtn = showcase.querySelector('.strip-prev');
        var nextBtn = showcase.querySelector('.strip-next');
        if (prevBtn) prevBtn.addEventListener('click', function() { strip.scrollBy({ left: -140, behavior: 'smooth' }); });
        if (nextBtn) nextBtn.addEventListener('click', function() { strip.scrollBy({ left: 140, behavior: 'smooth' }); });
    });

    // =======================
    // 分类标签切换
    // =======================
    var tabs = document.querySelectorAll('.cert-tab');
    tabs.forEach(function(tab) {
        tab.addEventListener('click', function() {
            var type = this.getAttribute('data-type');
            tabs.forEach(function(t) { t.classList.remove('active'); });
            this.classList.add('active');
            document.querySelectorAll('.cert-showcase').forEach(function(s) {
                s.style.display = 'none';
            });
            var target = document.getElementById('showcase-' + type);
            if (target) target.style.display = 'block';
        });
    });

    // =======================
    // 英雄区双展示框轮播（独立控制）
    // =======================
    var showcases = document.querySelectorAll('.hero-alt-showcases .hero-alt-showcase');
    showcases.forEach(function(showcaseEl) {
        var slider = showcaseEl.querySelector('.hero-showcase-slider');
        var dotsContainer = showcaseEl.querySelector('.hero-showcase-dots');
        if (!slider || !dotsContainer) return;
        var items = slider.querySelectorAll('.hero-showcase-item');
        var dots = dotsContainer.querySelectorAll('.hero-dot');
        if (items.length <= 1) return;

        var currentIdx = 0;
        var autoTimer = null;

        function showItem(idx) {
            if (idx < 0) idx = items.length - 1;
            if (idx >= items.length) idx = 0;
            items.forEach(function(item) { item.classList.remove('active'); });
            dots.forEach(function(d) { d.classList.remove('active'); });
            items[idx].classList.add('active');
            dots[idx].classList.add('active');
            currentIdx = idx;
        }

        function nextItem() { showItem(currentIdx + 1); }

        dots.forEach(function(dot, idx) {
            dot.addEventListener('click', function() {
                showItem(idx);
                resetAuto();
            });
        });

        function startAuto() {
            stopAuto();
            autoTimer = setInterval(nextItem, 4000);
        }
        function stopAuto() { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } }
        function resetAuto() { startAuto(); }

        showcaseEl.addEventListener('mouseenter', stopAuto);
        showcaseEl.addEventListener('mouseleave', startAuto);

        startAuto();
    });

    // =======================
    // AI 聊天组件
    // =======================
    var chatToggle = document.getElementById('chatToggle');
    var chatPanel = document.getElementById('chatPanel');
    var chatClose = document.getElementById('chatClose');
    var chatBody = document.getElementById('chatBody');
    var chatInput = document.getElementById('chatInput');
    var chatSend = document.getElementById('chatSend');

    if (chatToggle && chatPanel) {
        chatToggle.addEventListener('click', function() {
            chatPanel.classList.toggle('active');
            if (chatPanel.classList.contains('active') && chatInput) chatInput.focus();
        });
        chatClose.addEventListener('click', function() {
            chatPanel.classList.remove('active');
        });
    }

    function appendMsg(type, text) {
        var div = document.createElement('div');
        div.className = 'chat-msg ' + type;
        div.textContent = text;
        chatBody.appendChild(div);
        chatBody.scrollTop = chatBody.scrollHeight;
        return div;
    }

    function sendMessage() {
        var text = (chatInput.value || '').trim();
        if (!text) return;
        appendMsg('user', text);
        chatInput.value = '';
        var loading = appendMsg('loading', '思考中...');

        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            loading.remove();
            appendMsg('bot', d.reply);
        })
        .catch(function() {
            loading.remove();
            appendMsg('bot', '抱歉，服务暂时不可用，请稍后再试。');
        });
    }

    if (chatSend) chatSend.addEventListener('click', sendMessage);
    if (chatInput) chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
    });

    // =======================
    // 首页案例预览（AJAX 加载）
    // =======================
    var casesPreview = document.getElementById('casesPreview');
    if (casesPreview) {
        fetch('/api/cases/preview')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data.length) {
                    casesPreview.innerHTML = '<div class="empty-state">暂无案例展示</div>';
                    return;
                }
                var html = '';
                data.forEach(function(c) {
                    html += '<div class="case-card">' +
                        '<div class="case-card-header">' +
                            '<span class="case-type-badge">' + (c.case_type || '') + '</span>' +
                            '<span class="case-status">' + (c.case_status || '') + '</span>' +
                        '</div>' +
                        '<h3><a href="/cases/' + c.id + '">' + c.title + '</a></h3>' +
                        '<p class="case-desc">' + (c.description || '').substring(0, 100) + '...</p>' +
                        '<a href="/cases/' + c.id + '" class="read-more">查看详情 →</a>' +
                    '</div>';
                });
                casesPreview.innerHTML = html;
            })
            .catch(function() {
                casesPreview.innerHTML = '';
            });
    }

    // =======================
    // 智能咨询弹窗（15秒 + 退出意图）
    // =======================
    var smartPopup = document.getElementById('smartPopup');
    var smartPopupClose = document.getElementById('smartPopupClose');
    if (smartPopup && smartPopupClose) {
        var popupDismissed = sessionStorage.getItem('popupDismissed');
        var popupShown = false;

        function showPopup() {
            if (popupDismissed || popupShown) return;
            popupShown = true;
            smartPopup.style.display = 'flex';
            sessionStorage.setItem('popupShown', '1');
            if (typeof _hmt !== 'undefined') _hmt.push(['_trackEvent', 'popup', 'show', 'smart_consult']);
        }

        // 15秒后弹出
        if (!popupDismissed) {
            setTimeout(showPopup, 15000);
        }

        // 退出意图触发（鼠标移出页面顶部）
        if (!popupDismissed) {
            document.addEventListener('mouseout', function(e) {
                if (e.clientY < 10 && e.relatedTarget === null) {
                    showPopup();
                }
            }, { once: false });
        }

        smartPopupClose.addEventListener('click', function() {
            smartPopup.style.display = 'none';
            sessionStorage.setItem('popupDismissed', '1');
        });
        smartPopup.addEventListener('click', function(e) {
            if (e.target === smartPopup) {
                smartPopup.style.display = 'none';
                sessionStorage.setItem('popupDismissed', '1');
            }
        });
    }

    // =======================
    // 微信弹窗
    // =======================
    var wechatBtn = document.getElementById('mcbWechat');
    var wechatModal = document.getElementById('wechatModal');
    var wechatClose = document.getElementById('wechatModalClose');
    if (wechatBtn && wechatModal) {
        wechatBtn.addEventListener('click', function() {
            wechatModal.classList.add('active');
        });
        wechatClose.addEventListener('click', function() {
            wechatModal.classList.remove('active');
        });
        wechatModal.addEventListener('click', function(e) {
            if (e.target === wechatModal) wechatModal.classList.remove('active');
        });
    }

    // =======================
    // 小程序弹窗
    // =======================
    var miniappToggle = document.getElementById('miniappToggle');
    var miniappPopup = document.getElementById('miniappPopup');
    var miniappPopupClose = document.getElementById('miniappPopupClose');
    var mcbMiniapp = document.getElementById('mcbMiniapp');
    if (miniappToggle && miniappPopup) {
        miniappToggle.addEventListener('click', function() {
            miniappPopup.classList.toggle('active');
        });
        miniappPopupClose.addEventListener('click', function() {
            miniappPopup.classList.remove('active');
        });
    }
    if (mcbMiniapp && miniappPopup) {
        mcbMiniapp.addEventListener('click', function() {
            miniappPopup.classList.toggle('active');
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        });
    }
});
