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

  it('parses new CommonMark thought directives', () => {
    const blocks = parseMessageContent(
      'before\n\n:::thought\nI will compute **centrality**\n:::\n\nafter',
    );

    expect(blocks).toEqual([
      { type: 'text', content: 'before' },
      { type: 'thought', content: 'I will compute **centrality**', complete: true },
      { type: 'text', content: 'after' },
    ]);
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

  it('reads new steps and collapsible directives', () => {
    const blocks = parseMessageContent(
      ':::steps\nImporting\nLaying out\n:::\n\n' +
        ':::collapsible{title="Uploaded network" open="true"}\n- **Size:** 34\n:::',
    );

    expect(blocks).toEqual([
      {
        type: 'steps',
        steps: ['Importing', 'Laying out'],
        complete: true,
      },
      {
        type: 'collapsible',
        title: 'Uploaded network',
        open: true,
        content: '- **Size:** 34',
        complete: true,
      },
    ]);
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

  it('keeps directive tool markers in position', () => {
    const blocks = parseMessageContent(
      'Computing.\n\n::tool-execution{index="2"}\n\nDone.',
    );

    expect(blocks.map((b) => b.type)).toEqual(['text', 'tool', 'text']);
    expect(blocks[1].index).toBe(2);
  });

  it('renders each tool execution index only once if a model copied a marker', () => {
    const blocks = parseMessageContent(
      '::tool-execution{index="0"}\n\nThinking.\n\n' +
        '::tool-execution{index="0"}\n\nDone.',
    );

    expect(blocks.filter((block) => block.type === 'tool')).toEqual([
      { type: 'tool', index: 0 },
    ]);
    expect(blocks.at(-1)).toEqual({ type: 'text', content: 'Done.' });
  });

  it('hides invented visualization output tags from current and old messages', () => {
    expect(parseMessageContent(
      'Done.\n\n<visualization_output network_id="642" type="full"/>',
    )).toEqual([{ type: 'text', content: 'Done.' }]);
    expect(parseMessageContent(
      '&lt;visualization-output network_id="642"/&gt;Ready.',
    )).toEqual([{ type: 'text', content: 'Ready.' }]);
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
