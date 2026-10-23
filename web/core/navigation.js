import { icon } from '../icons.js';
import { $ } from './dom.js';

export function closeNavigation() {
  $('.sidebar').classList.remove('open');
  $('#mobile-menu').setAttribute('aria-expanded', 'false');
  $('#mobile-menu').setAttribute('aria-label', '打开导航');
  $('#mobile-menu').innerHTML = icon('menu');
  document.body.classList.remove('nav-open');
}

export function toggleNavigation() {
  const open = !$('.sidebar').classList.contains('open');
  if (!open) {
    closeNavigation();
    return;
  }
  $('.sidebar').classList.add('open');
  $('#mobile-menu').setAttribute('aria-expanded', 'true');
  $('#mobile-menu').setAttribute('aria-label', '关闭导航');
  $('#mobile-menu').innerHTML = icon('close');
  document.body.classList.add('nav-open');
  $('.nav-item.active').focus();
}
