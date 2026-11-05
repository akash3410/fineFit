(function () {
  const imgs = Array.from(document.querySelectorAll('img'));
  const viewport = { w: innerWidth, h: innerHeight };
  const groups = { noSrc: [], failed: [], hidden: [], zeroDim: [], ok: [] };
  const perf = performance.getEntriesByType('resource').filter(e => e.initiatorType === 'img');
  console.group('FineFit Homepage Image Diagnostic');
  imgs.forEach((img, i) => {
    const rect = img.getBoundingClientRect();
    const style = getComputedStyle(img);
    const parent = img.parentElement ? img.parentElement.getBoundingClientRect() : null;
    const inViewport = rect.bottom > 0 && rect.right > 0 && rect.top < viewport.h && rect.left < viewport.w;
    const info = {
      index: i,
      alt: img.alt || '(none)',
      src: img.src,
      currentSrc: img.currentSrc,
      complete: img.complete,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
      display: style.display,
      visibility: style.visibility,
      opacity: style.opacity,
      position: style.position,
      objectFit: style.objectFit,
      rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
      parent: parent ? { w: parent.width, h: parent.height } : null,
      inViewport
    };
    if (!img.src) groups.noSrc.push(info);
    else if (img.complete && img.naturalWidth === 0) groups.failed.push(info);
    else if (img.complete && img.naturalWidth > 0 && (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0 || rect.width === 0 || rect.height === 0)) groups.hidden.push(info);
    else if (img.complete && img.naturalWidth > 0 && (rect.width === 0 || rect.height === 0)) groups.zeroDim.push(info);
    else groups.ok.push(info);
    console.log('IMG', i, info);
  });
  console.group('Summary');
  console.log('Total imgs:', imgs.length);
  console.log('No src:', groups.noSrc.length, groups.noSrc);
  console.log('Failed (naturalWidth 0):', groups.failed.length, groups.failed);
  console.log('Loaded but visually hidden/zero rect:', groups.hidden.length, groups.hidden);
  console.log('Zero dimensions:', groups.zeroDim.length, groups.zeroDim);
  console.log('OK:', groups.ok.length, groups.ok);
  console.groupEnd();
  console.group('Performance image resources');
  perf.forEach(e => console.log(e.name, 'transferSize=', e.transferSize, 'duration=', e.duration));
  console.groupEnd();
  console.groupEnd();
})();
