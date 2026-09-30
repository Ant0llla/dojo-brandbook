(() => {
  'use strict';

  const MASTER = { width: 1920, height: 1080 };
  const MAX_FRAME_INTERVAL = 1000 / 30;
  const variants = [
    { key: '1', slug: 'oni', id: 'waiting-oni-breath', title: 'Дыхание маски' },
    { key: '2', slug: 'relay', id: 'waiting-red-relay', title: '12 колонн' },
    { key: '3', slug: 'wordmark', id: 'waiting-wordmark-cut', title: 'Срез слова' },
    { key: '4', slug: 'aperture', id: 'waiting-club-aperture', title: 'Окна клуба' }
  ];
  const copy = {
    preparing: ['ПОДГОТОВКА', 'Подключаемся к клубу', 'Игры и программы появятся после подготовки'],
    offline: ['НЕТ СВЯЗИ', 'Не удалось подключиться', 'Проверьте соединение или позовите администратора'],
    ready: ['ГОТОВО', 'Все готово к запуску', 'Можно продолжить в интерфейсе клуба'],
    maintenance: ['ОБСЛУЖИВАНИЕ', 'DOJO временно недоступен', 'Пожалуйста, позовите администратора'],
    error: ['ОШИБКА', 'Не удалось запустить DOJO', 'Попробуйте еще раз или позовите администратора']
  };

  const params = new URLSearchParams(location.search);
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.documentElement;
  const motionToggle = document.getElementById('motion-toggle');
  const stateControl = document.getElementById('state-control');
  const runtime = {
    state: copy[params.get('state')] ? params.get('state') : 'preparing',
    activeMs: 0,
    frameWrites: 0,
    lastTick: performance.now(),
    lastDraw: 0,
    animationFrame: 0,
    userPaused: false,
    hostPaused: false,
    gaming: false
  };

  function resolveVariant(value) {
    return variants.find(item => item.key === value || item.slug === value || item.id === value) || null;
  }

  const requested = resolveVariant(params.get('variant')) || resolveVariant(params.get('frame'));
  if (params.has('variant') && requested) {
    document.body.dataset.view = 'single';
    const card = document.querySelector('[data-variant-card="' + requested.key + '"]');
    if (card) card.classList.add('is-selected');
    document.title = requested.title + ' — DOJO';
  } else if (params.has('frame')) {
    document.body.dataset.view = 'frame';
  }

  document.querySelectorAll('[role="status"]').forEach(status => {
    status.setAttribute('aria-live', requested && status.closest('.motion-board')?.id === requested.id ? 'polite' : 'off');
  });

  function fitPreview(shell) {
    const board = shell.querySelector('.motion-board');
    if (!board || board.parentElement?.id === 'frame-stage') return;
    const bounds = shell.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const scale = Math.min(bounds.width / MASTER.width, bounds.height / MASTER.height);
    const renderedWidth = MASTER.width * scale;
    const renderedHeight = MASTER.height * scale;
    board.style.transform = 'scale(' + scale + ')';
    board.style.left = Math.max(0, (bounds.width - renderedWidth) / 2) + 'px';
    board.style.top = Math.max(0, (bounds.height - renderedHeight) / 2) + 'px';
  }

  const previewShells = [...document.querySelectorAll('.preview-shell')];
  const previewObserver = new ResizeObserver(entries => entries.forEach(entry => fitPreview(entry.target)));
  previewShells.forEach(shell => {
    previewObserver.observe(shell);
    fitPreview(shell);
  });
  addEventListener('resize', () => previewShells.forEach(fitPreview), { passive: true });
  document.fonts.ready.then(() => previewShells.forEach(fitPreview));

  function renderMotion(seconds) {
    const fullTurn = Math.PI * 2;
    root.style.setProperty('--oni-x', Math.sin(seconds * fullTurn / 12) * 3 + 'px');
    root.style.setProperty('--oni-y', Math.sin(seconds * fullTurn / 9.5) * 4 + 'px');
    root.style.setProperty('--oni-scale', String(1 + Math.sin(seconds * fullTurn / 12) * .004));
    root.style.setProperty('--oni-breath', String(.86 + Math.sin(seconds * fullTurn / 8) * .07));
    root.style.setProperty('--oni-shine-x', ((seconds % 12) / 12) * 100 + '%');

    const relayPhase = (seconds % 8) / 8;
    const relayPingPong = relayPhase <= .5 ? relayPhase * 2 : (1 - relayPhase) * 2;
    root.style.setProperty('--relay-x', relayPingPong * 1756 + 'px');

    const cutPhase = seconds % 8;
    if (cutPhase < .65) {
      const cutProgress = cutPhase / .65;
      const cutLeft = cutProgress * 92;
      root.style.setProperty('--cut-left', cutLeft + '%');
      root.style.setProperty('--cut-right', Math.max(0, 100 - cutLeft - 8) + '%');
      root.style.setProperty('--cut-opacity', String(Math.sin(Math.PI * cutProgress)));
    } else {
      root.style.setProperty('--cut-left', '46%');
      root.style.setProperty('--cut-right', '46%');
      root.style.setProperty('--cut-opacity', '0');
    }

    const aperture = Math.sin(seconds * fullTurn / 14) * 6;
    root.style.setProperty('--aperture-x', aperture + 'px');
    root.style.setProperty('--aperture-x-reverse', -aperture + 'px');
  }

  function isRuntimePaused() {
    return document.hidden || runtime.userPaused || runtime.hostPaused || runtime.gaming || reducedMotion.matches;
  }

  function syncPauseState() {
    const paused = isRuntimePaused();
    document.body.dataset.paused = String(runtime.userPaused);
    document.body.dataset.runtimePaused = String(paused);
    if (motionToggle) {
      motionToggle.setAttribute('aria-pressed', String(runtime.userPaused));
      motionToggle.textContent = runtime.userPaused ? 'Продолжить движение' : 'Остановить движение';
    }
    if (runtime.animationFrame) cancelAnimationFrame(runtime.animationFrame);
    runtime.animationFrame = 0;
    runtime.lastTick = performance.now();
    runtime.lastDraw = 0;
    if (!paused) runtime.animationFrame = requestAnimationFrame(draw);
    else renderMotion(runtime.activeMs / 1000);
  }

  function draw(now) {
    runtime.animationFrame = 0;
    if (isRuntimePaused()) return;
    const elapsed = Math.min(80, Math.max(0, now - runtime.lastTick));
    runtime.lastTick = now;
    runtime.activeMs += elapsed;
    if (now - runtime.lastDraw >= MAX_FRAME_INTERVAL) {
      renderMotion(runtime.activeMs / 1000);
      runtime.frameWrites += 1;
      runtime.lastDraw = now;
    }
    runtime.animationFrame = requestAnimationFrame(draw);
  }

  function setState(state) {
    if (!copy[state]) return false;
    runtime.state = state;
    document.body.dataset.state = state;
    const [eyebrow, title, text] = copy[state];
    document.querySelectorAll('[data-status-eyebrow]').forEach(node => { node.textContent = eyebrow; });
    document.querySelectorAll('[data-status-title]').forEach(node => { node.textContent = title; });
    document.querySelectorAll('[data-status-text]').forEach(node => { node.textContent = text; });
    if (stateControl && [...stateControl.options].some(option => option.value === state)) stateControl.value = state;
    return true;
  }

  function configure(patch = {}) {
    if ('hostPaused' in patch) runtime.hostPaused = Boolean(patch.hostPaused);
    if ('gaming' in patch) runtime.gaming = Boolean(patch.gaming);
    if ('state' in patch) setState(patch.state);
    syncPauseState();
    return context();
  }

  function context() {
    return {
      state: runtime.state,
      activeMs: runtime.activeMs,
      userPaused: runtime.userPaused,
      hostPaused: runtime.hostPaused,
      gaming: runtime.gaming,
      reducedMotion: reducedMotion.matches,
      hidden: document.hidden,
      selectedVariant: requested?.id || null
    };
  }

  motionToggle?.addEventListener('click', () => {
    runtime.userPaused = !runtime.userPaused;
    syncPauseState();
  });
  stateControl?.addEventListener('change', event => setState(event.target.value));
  document.addEventListener('visibilitychange', syncPauseState);
  reducedMotion.addEventListener('change', syncPauseState);

  window.DojoWaiting = {
    variants: variants.map(item => ({ ...item })),
    states: Object.keys(copy),
    context,
    metrics: () => ({ ...context(), frameWrites: runtime.frameWrites, animationRunning: Boolean(runtime.animationFrame) }),
    setState,
    configure,
    pause: () => { runtime.userPaused = true; syncPauseState(); },
    resume: () => { runtime.userPaused = false; syncPauseState(); },
    seek: milliseconds => {
      runtime.activeMs = Math.max(0, Number(milliseconds) || 0);
      renderMotion(runtime.activeMs / 1000);
      return runtime.activeMs;
    }
  };

  setState(runtime.state);
  renderMotion(0);
  syncPauseState();
})();
