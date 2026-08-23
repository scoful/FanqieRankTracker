/**
 * 四榜路径与 URL 工具
 * channel: female | male
 * board: new | read
 */
const Boards = (function () {
    const LABELS = {
        female: { new: '女频新书榜', read: '女频阅读榜' },
        male: { new: '男频新书榜', read: '男频阅读榜' },
    };

    const GENRE_GROUPS = {
        female: [
            { name: '古风言情', categories: ['古风世情', '古言脑洞', '宫斗宅斗', '种田'] },
            { name: '现代言情', categories: ['现言脑洞', '豪门总裁', '职场婚恋', '青春甜宠'] },
            { name: '幻想言情', categories: ['玄幻言情', '科幻末世', '悬疑脑洞', '女频悬疑'] },
            { name: '快穿衍生', categories: ['快穿', '女频衍生'] },
            { name: '年代民国', categories: ['年代', '民国言情'] },
            { name: '娱乐星光', categories: ['星光璀璨'] },
            { name: '游戏体育', categories: ['游戏体育'] },
        ],
        male: [
            { name: '都市脑洞', categories: ['都市日常', '都市脑洞', '都市种田', '都市修真', '都市高武'] },
            { name: '玄幻仙侠', categories: ['传统玄幻', '玄幻脑洞', '东方仙侠', '西方奇幻'] },
            { name: '历史军事', categories: ['历史古代', '历史脑洞', '抗战谍战'] },
            { name: '战神赘婿', categories: ['战神赘婿'] },
            { name: '科幻末世', categories: ['科幻末世'] },
            { name: '悬疑灵异', categories: ['悬疑灵异', '悬疑脑洞'] },
            { name: '游戏衍生', categories: ['游戏体育', '动漫衍生', '男频衍生'] },
        ],
    };

    const MARKET_KEYWORDS = {
        female: [
            '重生', '穿书', '快穿', '系统', '空间', '团宠', '萌宝', '幼崽', '女配', '炮灰',
            '反派', '权臣', '宅斗', '宫斗', '和离', '替嫁', '逃荒', '种田', '美食', '经商',
            '年代', '七零', '八零', '军婚', '豪门', '总裁', '真假千金', '先婚后爱', '追妻',
            '甜宠', '双洁', '强制爱', '无CP', '末世', '废土', '天灾', '囤货', '异能',
            '国运', '星际', '修仙', '玄学', '无限流', '悬疑', '直播', '综艺', '娱乐圈',
            '校园', '暗恋', '青梅竹马', '民国', '兽世', '远古', '基建',
        ],
        male: [
            '重生', '穿越', '系统', '签到', '无敌', '退婚', '赘婿', '战神', '兵王', '神医',
            '国运', '基建', '科技', '末日', '末世', '囤货', '异能', '修仙', '玄幻', '仙侠',
            '高武', '都市', '脑洞', '直播', '游戏', '电竞', '无限流', '诸天', '万界',
            '历史', '争霸', '权谋', '谍战', '抗战', '灵异', '悬疑', '犯罪', '种田', '经营',
            '多女主', '后宫', '无女主', '爽文', '打脸', '装逼', '升级', '练功', '功法',
        ],
    };

    function normalizeChannel(value) {
        return value === 'male' ? 'male' : 'female';
    }

    function normalizeBoard(value) {
        return value === 'read' ? 'read' : 'new';
    }

    function parseQuery(search) {
        const params = new URLSearchParams(search || window.location.search);
        return {
            channel: normalizeChannel(params.get('channel')),
            board: normalizeBoard(params.get('board')),
            type: params.get('type') || '',
            id: params.get('id') || '',
            title: params.get('title') || '',
        };
    }

    function buildQuery(state, extra) {
        const params = new URLSearchParams();
        params.set('channel', normalizeChannel(state.channel));
        params.set('board', normalizeBoard(state.board));
        const merged = Object.assign({}, extra || {});
        Object.keys(merged).forEach((key) => {
            const value = merged[key];
            if (value === undefined || value === null || value === '') {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        });
        // ensure channel/board not wiped if extra empty
        params.set('channel', normalizeChannel(state.channel));
        params.set('board', normalizeBoard(state.board));
        return params;
    }

    function replaceQuery(state, extra) {
        const params = buildQuery(state, extra);
        const url = `${window.location.pathname}?${params.toString()}`;
        history.replaceState(null, '', url);
        return params;
    }

    function label(channel, board) {
        return (LABELS[channel] && LABELS[channel][board]) || `${channel}/${board}`;
    }

    function datesUrl(channel, board) {
        return `data/dates/${channel}/${board}.json`;
    }

    function latestUrl(channel, board) {
        return `data/latest/${channel}/${board}.json`;
    }

    function snapshotUrl(channel, board, dateDash) {
        const compact = String(dateDash || '').replace(/-/g, '');
        return `data/${channel}/${board}/${compact}.json`;
    }

    function trendUrl(channel, board, dateDash) {
        return `data/trends/${channel}/${board}/${dateDash}.json`;
    }

    function marketUrl(channel, board) {
        return `data/market/${channel}/${board}.json`;
    }

    function apiIndexUrl(channel, board) {
        return `api/${channel}/${board}/index.json`;
    }

    function apiAllUrl(channel, board) {
        return `api/${channel}/${board}/all.json`;
    }

    function indexUrl(channel, board, extra) {
        const q = buildQuery({ channel, board }, extra);
        return `index.html?${q.toString()}`;
    }

    function trendPageUrl(channel, board, extra) {
        const q = buildQuery({ channel, board }, extra);
        return `trend.html?${q.toString()}`;
    }

    function bookPageUrl(channel, board, extra) {
        const q = buildQuery({ channel, board }, extra);
        return `book.html?${q.toString()}`;
    }

    function genreGroups(channel) {
        return GENRE_GROUPS[channel] || GENRE_GROUPS.female;
    }

    function marketKeywords(channel) {
        return MARKET_KEYWORDS[channel] || MARKET_KEYWORDS.female;
    }

    return {
        LABELS,
        normalizeChannel,
        normalizeBoard,
        parseQuery,
        buildQuery,
        replaceQuery,
        label,
        datesUrl,
        latestUrl,
        snapshotUrl,
        trendUrl,
        marketUrl,
        apiIndexUrl,
        apiAllUrl,
        indexUrl,
        trendPageUrl,
        bookPageUrl,
        genreGroups,
        marketKeywords,
    };
})();
