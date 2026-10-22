import { fireEvent, render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { describe, expect, it, vi } from 'vitest';
import NetworkDataChooser from '../components/NetworkDataChooser';


const samples = [
  {
    id: 'karate-club',
    name: "Zachary's Karate Club",
    description: 'A weighted friendship network.',
    node_count: 34,
    edge_count: 78,
    source_url: 'https://example.com/karate',
  },
];

const renderChooser = (overrides = {}) => {
  const props = {
    samples,
    catalogStatus: 'success',
    catalogError: null,
    busy: false,
    loadingSampleId: null,
    onUpload: vi.fn(),
    onSelectSample: vi.fn(),
    fileInputRef: createRef(),
    ...overrides,
  };
  render(<NetworkDataChooser {...props} />);
  return props;
};


describe('NetworkDataChooser', () => {
  it('shows sample metadata and selects a sample', () => {
    const props = renderChooser();

    expect(screen.getByText('34 nodes')).toBeInTheDocument();
    expect(screen.getByText('78 edges')).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', {
        name: "Load Zachary's Karate Club sample network",
      }),
    );

    expect(props.onSelectSample).toHaveBeenCalledWith('karate-club');
  });

  it('disables both input choices while a sample is loading', () => {
    renderChooser({ busy: true, loadingSampleId: 'karate-club' });

    expect(screen.getByRole('button', { name: 'Upload GraphML' })).toBeDisabled();
    expect(screen.getByText("Loading Zachary's Karate Club…")).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: "Load Zachary's Karate Club sample network",
      }),
    ).toBeDisabled();
  });

  it('reports a catalog loading error without hiding file upload', () => {
    renderChooser({
      samples: [],
      catalogStatus: 'error',
      catalogError: 'Catalog unavailable',
    });

    expect(screen.getByRole('alert')).toHaveTextContent('Catalog unavailable');
    expect(screen.getByRole('button', { name: 'Upload GraphML' })).toBeEnabled();
  });
});
