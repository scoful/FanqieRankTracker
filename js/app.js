document.addEventListener('DOMContentLoaded', () => {
    const categoryList = document.getElementById('category-list');
    const waterfall = document.getElementById('books-waterfall');
    const updateDate = document.getElementById('update-date');
    const categoryTitle = document.getElementById('current-category-title');
    const aiContent = document.getElementById('ai-content');
    const aiSource = document.getElementById('ai-source');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const dateDisplay = document.getElementById('date-display');
    const datePickerBtn = document.getElementById('date-picker-btn');
    const dateInput = document.getElementById('date-input');
    const datePrevBtn = document.getElementById('date-prev');
    const dateNextBtn = document.getElementById('date-next');
    const sidebarSubtitle = document.getElementById('sidebar-subtitle');
    const trendLinkBtn = document.getElementById('trend-link-btn');

    const query = Boards.parseQuery();
    let currentChannel = query.channel;
    let currentBoard = query.board;

    let allData = null;
    let typingTimer = null;
    let availableDates = [];
    let currentDateIndex = -1;
    let currentCategory = null;

    const cacheBuster = `v=${Math.floor(Date.now() / 600000)}`;

    const copyToast = document.createElement('div');
    copyToast.className = 'copy-toast';
    copyToast.textContent = '书本信息已复制';
    document.body.appendChild(copyToast);
    let toastTimer = null;

    function showCopyToast() {
        if (toastTimer) clearTimeout(toastTimer);
        copyToast.classList.add('show');
        toastTimer = setTimeout(() => copyToast.classList.remove('show'), 1800);
    }

    function copyBookInfo(e, book) {
        e.preventDefault();
        e.stopPropagation();
        const text = `${book.title}\n作者：${book.author}\n阅读量：${book.reads}\n简介：${book.intro || '无'}\n链接：${book.url || '无'}`;
        navigator.clipboard.writeText(text).then(() => {
            const btn = e.currentTarget;
            btn.classList.add('copied');
            btn.textContent = '已复制';
            showCopyToast();
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.textContent = '复制信息';
            }, 1500);
        }).catch(() => {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            showCopyToast();
        });
    }

    let overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('show');
    });

    overlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
    });

    function syncBoardUi() {
        const label = Boards.label(currentChannel, currentBoard);
        if (sidebarSubtitle) sidebarSubtitle.textContent = label;
        document.title = `${label} · 风向标 | 番茄榜单追踪`;
        document.querySelectorAll('[data-channel]').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.channel === currentChannel);
        });
        document.querySelectorAll('[data-board]').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.board === currentBoard);
        });
        if (trendLinkBtn) {
            trendLinkBtn.href = Boards.trendPageUrl(currentChannel, currentBoard);
        }
        Boards.replaceQuery({ channel: currentChannel, board: currentBoard });
    }

    function renderRankSkeleton(count) {
        let html = '';
        for (let i = 0; i < count; i += 1) {
            html += `
                <div class="book-card book-card-skeleton" aria-hidden="true">
                    <div class="book-cover skeleton-block"></div>
                    <div class="book-info">
                        <div class="skeleton-block skeleton-title"></div>
                        <div class="skeleton-block skeleton-meta"></div>
                        <div class="skeleton-block skeleton-line"></div>
                        <div class="skeleton-block skeleton-line short"></div>
                    </div>
                </div>`;
        }
        return html;
    }

    function showBoardLoading() {
        categoryList.innerHTML = '<li class="loading-item">加载中...</li>';
        waterfall.innerHTML = renderRankSkeleton(8);
        aiContent.innerHTML = '<span class="ai-loading">正在加载分析数据...</span>';
    }

    function switchSlice(channel, board) {
        const nextChannel = Boards.normalizeChannel(channel);
        const nextBoard = Boards.normalizeBoard(board);
        if (nextChannel === currentChannel && nextBoard === currentBoard) return;
        currentChannel = nextChannel;
        currentBoard = nextBoard;
        currentCategory = null;
        currentDateIndex = -1;
        availableDates = [];
        allData = null;
        showBoardLoading();
        syncBoardUi();
        bootstrapBoard();
    }

    document.querySelectorAll('[data-channel]').forEach((btn) => {
        btn.addEventListener('click', () => switchSlice(btn.dataset.channel, currentBoard));
    });
    document.querySelectorAll('[data-board]').forEach((btn) => {
        btn.addEventListener('click', () => switchSlice(currentChannel, btn.dataset.board));
    });

    function updateDateNav() {
        const isLatest = currentDateIndex === availableDates.length - 1;
        const isFirst = currentDateIndex <= 0;

        datePrevBtn.disabled = isFirst || availableDates.length === 0;
        dateNextBtn.disabled = isLatest || availableDates.length === 0;

        const currentDate = availableDates[currentDateIndex];
        dateDisplay.textContent = currentDate || '暂无日期';

        if (isLatest || availableDates.length === 0) {
            datePickerBtn.classList.remove('is-historical');
        } else {
            datePickerBtn.classList.add('is-historical');
        }
        updatePresetButtons();
    }

    const presetBtns = document.querySelectorAll('.preset-btn');

    function updatePresetButtons() {
        const isLatest = currentDateIndex === availableDates.length - 1;
        const isYesterday = availableDates.length >= 2 && currentDateIndex === availableDates.length - 2;

        presetBtns.forEach((btn) => {
            const preset = btn.dataset.preset;
            if (preset === 'latest' && isLatest) {
                btn.classList.add('active');
            } else if (preset === 'yesterday' && isYesterday) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    presetBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            const preset = btn.dataset.preset;
            if (preset === 'latest' && availableDates.length > 0) {
                currentDateIndex = availableDates.length - 1;
                loadDateData(availableDates[currentDateIndex]);
            } else if (preset === 'yesterday' && availableDates.length >= 2) {
                currentDateIndex = availableDates.length - 2;
                loadDateData(availableDates[currentDateIndex]);
            }
        });
    });

    datePrevBtn.addEventListener('click', () => {
        if (currentDateIndex > 0) {
            currentDateIndex--;
            loadDateData(availableDates[currentDateIndex]);
        }
    });

    dateNextBtn.addEventListener('click', () => {
        if (currentDateIndex < availableDates.length - 1) {
            currentDateIndex++;
            loadDateData(availableDates[currentDateIndex]);
        }
    });

    datePickerBtn.addEventListener('click', () => {
        dateInput.showPicker ? dateInput.showPicker() : dateInput.click();
    });

    dateInput.addEventListener('change', () => {
        const selected = dateInput.value;
        if (!selected) return;
        const idx = availableDates.indexOf(selected);
        if (idx !== -1) {
            currentDateIndex = idx;
            loadDateData(selected);
        } else if (availableDates.length > 0) {
            const nearest = availableDates.reduce((prev, curr) =>
                Math.abs(new Date(curr) - new Date(selected)) < Math.abs(new Date(prev) - new Date(selected)) ? curr : prev
            );
            currentDateIndex = availableDates.indexOf(nearest);
            loadDateData(nearest);
            showToast(`${selected} 无数据，已跳转至最近的 ${nearest}`);
        }
    });

    function bootstrapBoard() {
        syncBoardUi();
        const datesUrl = `${Boards.datesUrl(currentChannel, currentBoard)}?${cacheBuster}`;
        fetch(datesUrl)
            .then((r) => (r.ok ? r.json() : Promise.reject('No dates')))
            .then((idx) => {
                availableDates = idx.dates || [];
                if (availableDates.length > 0) {
                    dateInput.min = availableDates[0];
                    dateInput.max = availableDates[availableDates.length - 1];
                }
                return loadLatestData();
            })
            .catch(() => {
                console.warn('dates missing, try latest only');
                availableDates = [];
                loadLatestData();
            });
    }

    function loadLatestData() {
        showBoardLoading();
        const url = `${Boards.latestUrl(currentChannel, currentBoard)}?${cacheBuster}`;
        return fetch(url)
            .then((r) => {
                if (!r.ok) throw new Error('Network error');
                return r.json();
            })
            .then((data) => {
                allData = data;
                const latestDate = data.date;
                currentDateIndex = availableDates.indexOf(latestDate);
                if (currentDateIndex === -1 && latestDate) {
                    availableDates.push(latestDate);
                    availableDates.sort();
                    currentDateIndex = availableDates.indexOf(latestDate);
                }
                applyData(data);
            })
            .catch((err) => {
                console.error(err);
                updateDate.textContent = Boards.label(currentChannel, currentBoard);
                categoryList.innerHTML = '<li class="loading-item">暂无数据</li>';
                waterfall.innerHTML = `<p style="color:#f87171;padding:20px;">「${Boards.label(currentChannel, currentBoard)}」数据加载失败。请确认该榜已完成抓取与构建。</p>`;
                aiContent.innerHTML = '<span class="ai-loading">暂无分析数据</span>';
                updateDateNav();
            });
    }

    function loadDateData(dateStr) {
        const isLatest = currentDateIndex === availableDates.length - 1;
        if (isLatest) {
            loadLatestData();
            return;
        }

        waterfall.innerHTML = renderRankSkeleton(8);
        aiContent.innerHTML = '<span class="ai-loading">正在加载分析数据...</span>';
        const snapshotUrl = `${Boards.snapshotUrl(currentChannel, currentBoard, dateStr)}?${cacheBuster}`;
        const trendUrl = `${Boards.trendUrl(currentChannel, currentBoard, dateStr)}?${cacheBuster}`;

        Promise.all([
            fetch(snapshotUrl).then((r) => (r.ok ? r.json() : Promise.reject('No snapshot'))),
            fetch(trendUrl).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        ]).then(([snapshot, trendData]) => {
            const combined = {
                channel: currentChannel,
                board: currentBoard,
                date: snapshot.date,
                prev_date: trendData ? trendData.prev_date : '',
                categories: (snapshot.categories || []).map((cat) => ({
                    name: cat.name,
                    trend: trendData && trendData.trends ? (trendData.trends[cat.name] || {}) : {},
                    books: cat.books || [],
                })),
            };
            allData = combined;
            applyData(combined);
        }).catch((err) => {
            console.error('Failed to load historical data:', err);
            const nearest = findNearestAvailableDate(dateStr);
            if (nearest && nearest !== dateStr) {
                showToast(`${dateStr} 数据不可用，已跳转至 ${nearest}`);
                currentDateIndex = availableDates.indexOf(nearest);
                loadDateData(nearest);
            } else {
                waterfall.innerHTML = `<div class="empty-state">
                    <p>📭 该日期（${dateStr}）暂无数据</p>
                    <p class="empty-hint">可尝试切换到其他日期查看</p>
                </div>`;
                updateDateNav();
            }
        });
    }

    function findNearestAvailableDate(targetDate) {
        if (availableDates.length === 0) return null;
        return availableDates.reduce((prev, curr) =>
            Math.abs(new Date(curr) - new Date(targetDate)) < Math.abs(new Date(prev) - new Date(targetDate)) ? curr : prev
        );
    }

    function showToast(msg) {
        copyToast.textContent = msg;
        if (toastTimer) clearTimeout(toastTimer);
        copyToast.classList.add('show');
        toastTimer = setTimeout(() => {
            copyToast.classList.remove('show');
            copyToast.textContent = '书本信息已复制';
        }, 2500);
    }

    function applyData(data) {
        const prevInfo = data.prev_date ? ` (对比 ${data.prev_date})` : '';
        updateDate.textContent = `${data.date || ''}${prevInfo}`;
        updateDateNav();

        const savedCategory = currentCategory;
        renderCategories();

        const categoryExists = savedCategory && data.categories.some((c) => c.name === savedCategory);
        if (categoryExists) {
            selectCategory(savedCategory);
            document.querySelectorAll('#category-list li').forEach((el) => {
                el.classList.toggle('active', el.dataset.category === savedCategory);
            });
        } else if (data.categories.length > 0) {
            selectCategory(data.categories[0].name);
        } else {
            categoryTitle.textContent = '暂无分类';
            waterfall.innerHTML = '<p style="color:var(--text-muted);padding:20px;">该榜暂无分类数据。</p>';
            aiContent.innerHTML = '<span class="ai-loading">暂无分析数据</span>';
        }
    }

    function renderCategories() {
        categoryList.innerHTML = '';
        if (!allData || !allData.categories) return;

        allData.categories.forEach((cat, i) => {
            const li = document.createElement('li');
            li.dataset.category = cat.name;

            const nameSpan = document.createElement('span');
            nameSpan.textContent = cat.name;
            li.appendChild(nameSpan);

            const trend = cat.trend || {};
            if (trend.new_count > 0) {
                const badge = document.createElement('span');
                badge.className = 'cat-badge new';
                badge.textContent = `+${trend.new_count}`;
                li.appendChild(badge);
            }

            if ((currentCategory && cat.name === currentCategory) || (!currentCategory && i === 0)) {
                li.classList.add('active');
            }

            li.addEventListener('click', () => {
                document.querySelectorAll('#category-list li').forEach((el) => el.classList.remove('active'));
                li.classList.add('active');
                selectCategory(cat.name);
                sidebar.classList.remove('open');
                overlay.classList.remove('show');
            });

            categoryList.appendChild(li);
        });
    }

    function selectCategory(categoryName) {
        currentCategory = categoryName;
        categoryTitle.textContent = categoryName;
        const cat = allData.categories.find((c) => c.name === categoryName);
        if (!cat) return;
        renderTrend(cat);
        renderBooks(cat);
    }

    function buildPrevRankMap(categoryName) {
        const cat = allData.categories.find((c) => c.name === categoryName);
        if (!cat || !cat.trend) return {};

        const map = {};
        (cat.trend.new_books || []).forEach((title) => {
            map[title] = 'new';
        });
        (cat.trend.top_risers || []).forEach((r) => {
            map[r.title] = r.change;
        });
        (cat.trend.top_fallers || []).forEach((f) => {
            map[f.title] = f.change;
        });
        return map;
    }

    function renderTrend(cat) {
        const trend = cat.trend || {};
        const summary = trend.summary || '';
        if (aiSource) {
            if (trend.source === 'ai') {
                aiSource.textContent = 'AI 总结';
                aiSource.className = 'ai-source';
            } else if (trend.source === 'rule') {
                aiSource.textContent = '规则统计 · 非AI生成';
                aiSource.className = 'ai-source ai-source-rule';
            } else {
                aiSource.textContent = '';
                aiSource.className = 'ai-source ai-source-hidden';
            }
        }
        typewriterEffect(summary);
    }

    function renderMarkdown(text) {
        let html = escapeHtml(text);
        html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:1.05rem; margin:1em 0 0.5em; color:var(--text-primary);">$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:1.15rem; margin:1em 0 0.5em; color:var(--text-primary);">$1</h2>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/《(.+?)》/g, '<span style="color:var(--accent);font-weight:500">《$1》</span>');
        html = html.replace(/^[-*] (.+)$/gm, '<span style="display:block;padding-left:1em;text-indent:-0.6em">• $1</span>');
        html = html.replace(/^(\d+)\. (.+)$/gm, '<span style="display:block;padding-left:1em;text-indent:-0.6em">$1. $2</span>');
        return html;
    }

    function typewriterEffect(text) {
        if (typingTimer) {
            clearTimeout(typingTimer);
            typingTimer = null;
        }
        aiContent.innerHTML = '';
        if (!text) {
            aiContent.innerHTML = '<span class="ai-loading">暂无分析数据</span>';
            return;
        }
        aiContent.innerHTML = renderMarkdown(text);
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\n/g, '<br>');
    }

    function renderBooks(cat) {
        waterfall.innerHTML = '';
        const books = cat.books || [];

        if (books.length === 0) {
            waterfall.innerHTML = '<p style="color:var(--text-muted);padding:20px;">该分类暂无书籍。</p>';
            return;
        }

        const changeMap = buildPrevRankMap(cat.name);
        const fragment = document.createDocumentFragment();

        books.forEach((book, index) => {
            const rank = index + 1;
            const card = document.createElement('a');
            const bookId = extractBookId(book.url);
            card.href = bookId
                ? Boards.bookPageUrl(currentChannel, currentBoard, { id: bookId })
                : 'javascript:void(0)';
            card.rel = 'noopener';
            card.className = 'book-card';

            let rankCls = '';
            if (rank === 1) rankCls = 'rank-1';
            else if (rank === 2) rankCls = 'rank-2';
            else if (rank === 3) rankCls = 'rank-3';

            let changeHtml = '';
            const change = changeMap[book.title];
            if (change === 'new') {
                changeHtml = '<span class="book-change new">NEW</span>';
            } else if (change && String(change).startsWith('+')) {
                changeHtml = `<span class="book-change up">↑${change}</span>`;
            } else if (change && String(change).startsWith('-')) {
                changeHtml = `<span class="book-change down">↓${String(change).replace('-', '')}</span>`;
            }

            const coverHtml = book.cover
                ? `<div class="book-cover"><img src="${book.cover}" alt="${escapeAttr(book.title)}" loading="lazy"></div>`
                : `<div class="book-cover"><div class="no-cover">暂无封面</div></div>`;

            card.innerHTML = `
                <span class="book-rank ${rankCls}">${rank}</span>
                ${changeHtml}
                ${coverHtml}
                <div class="book-info">
                    <h3 class="book-title" title="${escapeAttr(book.title)}">${escapeHtml(book.title)}</h3>
                    <div class="book-meta">
                        <span class="book-author">${escapeHtml(book.author)}</span>
                        <span class="book-reads">${escapeHtml(book.reads)}</span>
                    </div>
                    <p class="book-intro">${escapeHtml(book.intro)}</p>
                    <button class="book-copy-btn" type="button">复制信息</button>
                </div>
            `;

            const copyBtn = card.querySelector('.book-copy-btn');
            copyBtn.addEventListener('click', (e) => copyBookInfo(e, book));
            fragment.appendChild(card);
        });

        waterfall.appendChild(fragment);
    }

    function escapeAttr(str) {
        return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function extractBookId(url) {
        const match = String(url || '').match(/\/page\/(\d+)/);
        return match ? match[1] : '';
    }

    bootstrapBoard();
});
