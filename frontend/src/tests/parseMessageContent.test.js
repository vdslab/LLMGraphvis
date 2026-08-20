import { describe, it, expect } from 'vitest';
import { parseMessageContent } from '../utils/parseMessageContent';

describe('parseMessageContent', () => {
  it('returns plain prose as a single text block', () => {
    expect(parseMessageContent('Hello there')).toEqual([
      { type: 'text', content: 'Hello there' },
    ]);
  });

  it('separates a thought from the prose around it', () => {
    const blocks = parseMessageContent(
      'before<thought>I will compute centrality</thought>after',
    );

    expect(blocks.map((b) => b.type)).toEqual(['text', 'thought', 'text']);
    expect(blocks[1]).toMatchObject({
      content: 'I will compute centrality',
      complete: true,
    });
  });

  it('recognizes escaped or loosely formatted thought tags', () => {
    const blocks = parseMessageContent(
      '&lt; Thought &gt;private plan&lt; /Thought &gt;answer',
    );

    expect(blocks).toEqual([
      { type: 'thought', content: 'private plan', complete: true },
      { type: 'text', content: 'answer' },
    ]);
  });

  it('marks an unclosed block incomplete rather than dropping it', () => {
    // Messages stream in, so the closing tag may simply not have arrived yet.
    const [block] = parseMessageContent('<thought>still writ');

    expect(block).toEqual({ type: 'thought', content: 'still writ', complete: false });
  });

  it('reads a steps block as one entry per line', () => {
    const [block] = parseMessageContent('<steps>Importing\nLaying out\n</steps>');

    expect(block.steps).toEqual(['Importing', 'Laying out']);
  });

  it('does not report steps as thinking', () => {
    // The whole point of the block: the upload pipeline does no reasoning.
    const blocks = parseMessageContent('<steps>Importing</steps>');

    expect(blocks.map((b) => b.type)).toEqual(['steps']);
  });

  it('reads a collapsible title and its default state', () => {
    const [block] = parseMessageContent(
      '<collapsible title="Uploaded network — 77 nodes">- **Size:** 77</collapsible>',
    );

    expect(block).toMatchObject({
      type: 'collapsible',
      title: 'Uploaded network — 77 nodes',
      open: false,
      content: '- **Size:** 77',
    });
  });

  it('honours an explicitly open collapsible', () => {
    const [block] = parseMessageContent(
      '<collapsible title="T" open="true">body</collapsible>',
    );

    expect(block.open).toBe(true);
  });

  it('keeps tool markers in position so results render where they ran', () => {
    const blocks = parseMessageContent(
      'Computing.\n\n<tool_execution_marker index="0"/>\n\nDone.',
    );

    expect(blocks.map((b) => b.type)).toEqual(['text', 'tool', 'text']);
    expect(blocks[1].index).toBe(0);
  });

  it('handles a full turn of interleaved blocks', () => {
    const blocks = parseMessageContent(
      '<thought>plan</thought>\n\nRunning.\n\n<tool_execution_marker index="0"/>\n\n' +
        '<thought>done</thought>\n\nResult.',
    );

    expect(blocks.map((b) => b.type)).toEqual([
      'thought',
      'text',
      'tool',
      'thought',
      'text',
    ]);
  });

  it('returns nothing for empty content', () => {
    expect(parseMessageContent('')).toEqual([]);
    expect(parseMessageContent(null)).toEqual([]);
  });
});
