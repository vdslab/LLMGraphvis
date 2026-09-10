import { render, screen } from '@testing-library/react';
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
});
