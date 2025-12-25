import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatInterface from '../components/ChatInterface';
import { useChatStore } from '../stores/chatStore';
import { useNetworkStore } from '../stores/networkStore';

// Mock mocks
vi.mock('../stores/chatStore');
vi.mock('../stores/networkStore');
vi.mock('react-markdown', () => ({ default: ({ children }) => <div>{children}</div> }));
vi.mock('remark-gfm', () => ({ default: () => {} }));
vi.mock('remark-breaks', () => ({ default: () => {} }));

describe('ChatInterface', () => {
    const mockSendMessage = vi.fn();
    
    beforeEach(() => {
        vi.clearAllMocks();
        
        // Setup default store mocks
        useChatStore.mockReturnValue({
            messages: [],
            sendMessage: mockSendMessage,
            isLoading: false,
            thinkingMessage: null,
            uploadNetwork: vi.fn(),
            chatId: 1
        });
        
        useNetworkStore.mockReturnValue({
            nodes: []
        });
    });

    it('renders input area', () => {
        render(<ChatInterface />);
        expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
    });

    it('updates input value on change', () => {
        render(<ChatInterface />);
        const input = screen.getByPlaceholderText('Type a message...');
        fireEvent.change(input, { target: { value: 'Hello' } });
        expect(input.value).toBe('Hello');
    });

    it('sends message on Enter without Shift', async () => {
        render(<ChatInterface />);
        const input = screen.getByPlaceholderText('Type a message...');
        
        fireEvent.change(input, { target: { value: 'Hello' } });
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false, code: 'Enter' });
        
        expect(mockSendMessage).toHaveBeenCalledWith('Hello');
        await waitFor(() => {
            expect(input.value).toBe('');
        });
    });

    it('does NOT send message on Shift+Enter', () => {
        render(<ChatInterface />);
        const input = screen.getByPlaceholderText('Type a message...');
        
        fireEvent.change(input, { target: { value: 'Line 1' } });
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: true, code: 'Enter' });
        
        expect(mockSendMessage).not.toHaveBeenCalled();
    });
});
