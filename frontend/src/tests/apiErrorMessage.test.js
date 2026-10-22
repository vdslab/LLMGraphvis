import { describe, expect, it } from 'vitest';
import { getApiErrorMessage } from '../services/api';


describe('getApiErrorMessage', () => {
  it('flattens FastAPI validation errors into renderable text', () => {
    const error = {
      message: 'Request failed',
      response: {
        data: {
          detail: [
            { type: 'int_parsing', loc: ['path', 'chat_id'], msg: 'Invalid ID' },
            { type: 'missing', loc: ['body'], msg: 'Field required' },
          ],
        },
      },
    };

    expect(getApiErrorMessage(error)).toBe('Invalid ID, Field required');
  });
});
