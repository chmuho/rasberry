const logList = document.getElementById('logList');
const btnOpen = document.getElementById('btnOpen');
const btnClose = document.getElementById('btnClose');
const btnAlerts = document.getElementById('btnAlerts');
const btnInstall = document.getElementById('btnInstall');
const btnRefresh = document.getElementById('btnRefresh');
const btnRegisterFace = document.getElementById('btnRegisterFace');
const btnAdmin = document.getElementById('btnAdmin');
const liveViewCard = document.getElementById('liveViewCard');
const liveViewModal = document.getElementById('liveViewModal');
const liveViewModalClose = document.getElementById('liveViewModalClose');
const liveViewModalImage = document.getElementById('liveViewModalImage');
const btnRefreshLiveView = document.getElementById('btnRefreshLiveView');
const adminLogsSection = document.getElementById('adminLogsSection');
const registerModal = document.getElementById('modalBackdrop');
const modalClose = document.getElementById('modalClose');
const latestTime = document.getElementById('latestTime');
const intrusionCount = document.getElementById('intrusionCount');
const intrusionDetail = document.getElementById('intrusionDetail');
const liveViewStatus = document.getElementById('liveViewStatus');
const liveViewImage = document.getElementById('liveViewImage');

let alertEnabled = false;
let deferredPrompt = null;
let lastLogTime = null;

const statusLabel = {
    ACCESS: '출입 허용',
    INTRUSION: '침입 감지',
    REMOTE_OPEN: '원격 열기',
    REMOTE_CLOSE: '원격 닫기'
};

const statusStyle = {
    ACCESS: 'bg-emerald-100 text-emerald-900',
    INTRUSION: 'bg-rose-100 text-rose-900',
    REMOTE_OPEN: 'bg-blue-100 text-blue-900',
    REMOTE_CLOSE: 'bg-slate-100 text-slate-900'
};

function getStatusLabel(status) {
    return statusLabel[status] || '알 수 없음';
}

function getStatusClass(status) {
    return statusStyle[status] || 'bg-slate-100 text-slate-900';
}

async function requestPermission() {
    if (!('Notification' in window)) {
        alert('이 브라우저는 알림을 지원하지 않습니다.');
        return;
    }

    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
        alertEnabled = true;
        btnAlerts.textContent = '푸시 알림 사용 중';
        btnAlerts.classList.add('active');
        notify('알림 활성화', '새 출입 기록이 도착하면 푸시 알림을 받습니다.');
    } else {
        alertEnabled = false;
        btnAlerts.textContent = '푸시 알림 켜기';
        btnAlerts.classList.remove('active');
    }
}

function notify(title, body) {
    if (!alertEnabled || !('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;

    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.ready.then(reg => {
            reg.showNotification(title, {
                body,
                icon: '/static/test.jpg',
                badge: '/static/test.jpg',
                vibrate: [100, 50, 100]
            });
        });
    } else {
        new Notification(title, {
            body,
            icon: '/static/test.jpg'
        });
    }
}

function createLogCard(log) {
    const card = document.createElement('article');
    card.className = 'rounded-3xl border border-slate-800 bg-slate-950/80 p-4 shadow-xl shadow-slate-950/20';

    const row = document.createElement('div');
    row.className = 'flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between';

    const meta = document.createElement('div');
    meta.className = 'space-y-2';

    const name = document.createElement('p');
    name.className = 'text-lg font-semibold text-white';
    name.textContent = log.name;

    const time = document.createElement('p');
    time.className = 'text-sm text-slate-400';
    time.textContent = log.time;

    meta.appendChild(name);
    meta.appendChild(time);

    const badge = document.createElement('span');
    badge.className = `inline-flex rounded-full px-3 py-1 text-sm font-semibold ${getStatusClass(log.status)}`;
    badge.textContent = getStatusLabel(log.status);

    row.appendChild(meta);
    row.appendChild(badge);
    card.appendChild(row);

    if (log.image) {
        const imageWrapper = document.createElement('div');
        imageWrapper.className = 'mt-4 overflow-hidden rounded-3xl border border-slate-800 bg-slate-950';
        const image = document.createElement('img');
        image.src = '/' + log.image;
        image.alt = log.name;
        image.className = 'h-48 w-full object-cover';
        imageWrapper.appendChild(image);
        card.appendChild(imageWrapper);
    }

    return card;
}

async function fetchLogs() {
    try {
        const response = await fetch('/logs');
        const logs = await response.json();
        renderLogs(logs);
        return logs;
    } catch (error) {
        console.error('로그 가져오기 실패', error);
        logList.innerHTML = '<p class="text-center text-sm text-slate-400">서버 연결에 실패했습니다.</p>';
        return [];
    }
}

function renderLogs(logs) {
    logList.innerHTML = '';
    if (!logs || logs.length === 0) {
        logList.innerHTML = '<p class="text-center text-sm text-slate-400">기록이 없습니다.</p>';
        latestTime.textContent = '-';
        intrusionCount.textContent = '0';
        intrusionDetail.textContent = '현재 수집된 침입 기록이 없습니다.';
        liveViewStatus.textContent = '대기 중';
        liveViewImage.src = '/static/test.jpg';
        return;
    }

    const displayLogs = logs.slice(0, 10);
    displayLogs.forEach(log => logList.appendChild(createLogCard(log)));

    const newest = logs[0];
    const intrusionLogs = logs.filter(item => item.status === 'INTRUSION');
    latestTime.textContent = newest.time || '-';
    intrusionCount.textContent = intrusionLogs.length.toString();
    intrusionDetail.textContent = intrusionLogs.length > 0 ? `마지막 침입: ${intrusionLogs[0].name} / ${intrusionLogs[0].time}` : '현재 수집된 침입 기록이 없습니다.';
    liveViewStatus.textContent = getStatusLabel(newest.status);
    liveViewImage.src = newest.image ? '/' + newest.image : '/static/test.jpg';

    if (lastLogTime && newest.time !== lastLogTime) {
        notify('새 출입 기록', `${newest.name} - ${getStatusLabel(newest.status)}`);
    }
    lastLogTime = newest.time;
}

async function controlDoor(action) {
    try {
        const response = await fetch('/api/door_control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
        const data = await response.json();
        if (response.ok) {
            alert(data.message);
            await fetchLogs();
        } else {
            alert(`원격 제어 실패: ${data.error}`);
        }
    } catch (error) {
        console.error('원격 제어 오류', error);
        alert('원격 제어 요청에 실패했습니다.');
    }
}

function openModal() {
    registerModal.classList.remove('hidden');
}

function closeModalWindow() {
    registerModal.classList.add('hidden');
}

function openLiveViewModal() {
    liveViewModal.classList.remove('hidden');
    // 라이브 뷰 이미지 업데이트
    liveViewModalImage.src = liveViewImage.src;
}

function closeLiveViewModal() {
    liveViewModal.classList.add('hidden');
}

function toggleAdminLogs() {
    adminLogsSection.classList.toggle('hidden');
    if (!adminLogsSection.classList.contains('hidden')) {
        fetchLogs(); // 관리자 로그 열 때 최신 데이터 로드
    }
}

async function refreshLiveView() {
    // 실제로는 라즈베리파이에서 실시간 스트림을 받아와야 함
    // 현재는 최신 로그 이미지로 대체
    const logs = await fetchLogs();
    if (logs && logs.length > 0) {
        liveViewModalImage.src = logs[0].image ? '/' + logs[0].image : '/static/test.jpg';
    }
}

async function installApp() {
    if (!deferredPrompt) {
        alert('설치 옵션을 사용할 수 없습니다.');
        return;
    }
    deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    if (choice.outcome === 'accepted') {
        btnInstall.textContent = '설치됨';
    }
    deferredPrompt = null;
}

btnOpen.addEventListener('click', () => controlDoor('open'));
btnClose.addEventListener('click', () => controlDoor('close'));
btnAlerts.addEventListener('click', () => requestPermission());
btnRefresh.addEventListener('click', () => fetchLogs());
btnInstall.addEventListener('click', () => installApp());
btnRegisterFace.addEventListener('click', () => openModal());
btnAdmin.addEventListener('click', () => toggleAdminLogs());
liveViewCard.addEventListener('click', () => openLiveViewModal());
liveViewModalClose.addEventListener('click', () => closeLiveViewModal());
btnRefreshLiveView.addEventListener('click', () => refreshLiveView());
modalClose.addEventListener('click', () => closeModalWindow());
registerModal.addEventListener('click', (event) => {
    if (event.target === registerModal) closeModalWindow();
});
liveViewModal.addEventListener('click', (event) => {
    if (event.target === liveViewModal) closeLiveViewModal();
});

window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !registerModal.classList.contains('hidden')) {
        closeModalWindow();
    }
    if (event.key === 'Escape' && !liveViewModal.classList.contains('hidden')) {
        closeLiveViewModal();
    }
});

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    btnInstall.classList.remove('hidden');
});

window.addEventListener('load', async () => {
    if ('serviceWorker' in navigator) {
        try {
            await navigator.serviceWorker.register('/static/service-worker.js', { scope: '/' });
            console.log('Service Worker 등록 완료');
        } catch (error) {
            console.error('Service Worker 등록 실패', error);
        }
    }

    if (Notification.permission === 'granted') {
        alertEnabled = true;
        btnAlerts.textContent = '푸시 알림 사용 중';
        btnAlerts.classList.add('active');
    }

    await fetchLogs();
    setInterval(fetchLogs, 15000);
});