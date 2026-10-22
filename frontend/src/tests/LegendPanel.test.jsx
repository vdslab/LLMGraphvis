import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import LegendPanel from '../components/LegendPanel';
import { useNetworkStore } from '../stores/networkStore';


beforeEach(() => useNetworkStore.getState().reset());


describe('LegendPanel', () => {
  it('shows the categorical palette returned by the backend', () => {
    useNetworkStore.setState({
      legend: {
        node_color: {
          attribute: 'club',
          type: 'categorical',
          palette: 'tableau10',
          mapping: { 'Mr. Hi': '#4e79a7', Officer: '#f28e2c' },
        },
      },
    });

    render(<LegendPanel />);

    expect(screen.getByText('Palette: tableau10')).toBeInTheDocument();
    expect(screen.getByText('Mr. Hi')).toBeInTheDocument();
    expect(screen.getByText('Officer')).toBeInTheDocument();
  });

  it('shows the current drawing quality with details on demand', () => {
    useNetworkStore.getState().setNetworkData({
      nodes: [{ id: 'a' }],
      links: [],
      legend: { layout: 'spring' },
      layout_quality: {
        layout: 'spring',
        issues: ['node_overlap', 'outliers_compress_core'],
        node_overlap: 0.125,
        crossings: 8,
        crossings_sampled: false,
        core_extent: 0.1,
        edge_length_cv: 0.7,
        aspect: 1.2,
      },
    });

    render(<LegendPanel />);

    expect(screen.getByText('Some nodes overlap')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Readability details'));
    expect(screen.getByText('13%')).toBeInTheDocument();
    expect(screen.getByText('Outlying nodes squeeze the center')).toBeInTheDocument();

    act(() => useNetworkStore.getState().setNetworkData({
      nodes: [], links: [], legend: { layout: 'spring' },
    }));
    expect(useNetworkStore.getState().layoutQuality).toBeNull();
  });
});
