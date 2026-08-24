// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand(); // Раскрыть на весь экран

// Данные для примера (потом заменим на реальный API)
const gpuOffers = [
    {
        platform: 'Vast.ai',
        gpu: 'RTX 4090',
        vram: '24GB',
        price: 0.25,
        priceHour: '$0.25/час',
        link: 'https://vast.ai'
    },
    {
        platform: 'RunPod',
        gpu: 'RTX 3090',
        vram: '24GB',
        price: 0.20,
        priceHour: '$0.20/час',
        link: 'https://runpod.io'
    },
    {
        platform: 'Lambda Labs',
        gpu: 'A100',
        vram: '40GB',
        price: 1.10,
        priceHour: '$1.10/час',
        link: 'https://lambdalabs.com'
    }
];

// Показ вкладок
function showTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');
    
    if (tabName === 'gpu') loadGPUOffers();
    if (tabName === 'compare') loadCompare();
}

// Загрузка GPU предложений
async function loadGPUOffers() {
    const container = document.getElementById('gpu-list');
    
    try {
        // Здесь потом будет реальный API запрос
        const html = gpuOffers.map(offer => `
            <div class="card">
                <div class="card-header">
                    <div class="gpu-name">${offer.gpu}</div>
                    <div class="gpu-price">${offer.priceHour}</div>
                </div>
                <div class="card-info">🖥 Платформа: ${offer.platform}</div>
                <div class="card-info">💾 VRAM: ${offer.vram}</div>
                <button class="btn-secondary" onclick="window.open('${offer.link}', '_blank')">
                     Арендовать
                </button>
            </div>
        `).join('');
        
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<div class="card">❌ Ошибка загрузки</div>';
    }
}

// Загрузка сравнения
async function loadCompare() {
    const container = document.getElementById('compare-list');
    
    const platforms = [
        { name: 'Vast.ai', minPrice: '$0.15/час', rating: '4.5⭐' },
        { name: 'RunPod', minPrice: '$0.20/час', rating: '4.7⭐' },
        { name: 'Lambda', minPrice: '$0.50/час', rating: '4.8⭐' },
        { name: 'Crusoe', minPrice: '$0.30/час', rating: '4.3⭐' }
    ];
    
    const html = platforms.map(p => `
        <div class="card">
            <div class="card-header">
                <div class="gpu-name">${p.name}</div>
                <div class="gpu-price">${p.rating}</div>
            </div>
            <div class="card-info"> От ${p.minPrice}</div>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

// Подключение кошелька
function connectWallet() {
    tg.showAlert('Подключение кошелька TON будет доступно в следующей версии!');
}

// Инициализация при загрузке
window.onload = () => {
    loadGPUOffers();
    
    // Настройка цветов под тему Telegram
    if (tg.themeParams) {
        document.body.style.background = tg.themeParams.bg_color || '#1e3c72';
    }
};
