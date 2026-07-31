import '@testing-library/jest-dom';

// jsdom implements no scrolling at all, so the chat panel's "follow the
// conversation" effect would throw on mount in every test that renders it.
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = function scrollTo() {};
}
