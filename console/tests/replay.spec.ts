/**
 * Render test: the App loads the demo bundle (fetch mocked to the committed
 * file), renders the expected record/finding counts, and the receipt panel
 * reaches its live-verified state. Runs under vitest + jsdom.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { createElement } from 'react';
import App, { safeBundlePath } from '../src/App';

const demo = readFileSync(resolve(__dirname, '../public/bundles/demo.jsonl'), 'utf8');

describe('console replay (demo bundle)', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        expect(url).toBe('bundles/demo.jsonl');
        return new Response(demo, { status: 200 });
      }),
    );
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders the demo run with its findings, mismatch and a verified receipt', async () => {
    render(createElement(App));
    expect((await screen.findAllByText('20261026-140211-7c3a', { exact: false })).length).toBeGreaterThan(0);
    expect(document.documentElement.dataset.simulated).toBe('true');

    const findings = screen.getByRole('complementary', { name: 'Findings' });
    expect(within(findings).getAllByRole('article')).toHaveLength(4);
    expect(within(findings).getByText('4 of 4', { exact: false })).toBeTruthy();

    expect(screen.getAllByText('30 records', { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /^Jump to record/ }).length).toBeGreaterThan(0);
    expect(document.querySelectorAll('[data-seq]')).toHaveLength(30);
    expect(screen.getByText('The agent’s account does not match the record.')).toBeTruthy();
    expect(screen.getByText('29 links')).toBeTruthy();
    expect(await screen.findByText('Signature verified', {}, { timeout: 3000 })).toBeTruthy();
  });

  it('only accepts same-origin relative .jsonl bundle paths', () => {
    expect(safeBundlePath('bundles/run-1.jsonl')).toBe('bundles/run-1.jsonl');
    expect(safeBundlePath('https://evil.example/x.jsonl')).toBeNull();
    expect(safeBundlePath('//evil.example/x.jsonl')).toBeNull();
    expect(safeBundlePath('../secrets.jsonl')).toBeNull();
    expect(safeBundlePath('/abs.jsonl')).toBeNull();
    expect(safeBundlePath('bundles/x.json')).toBeNull();
  });
});
