#!/usr/bin/env python3
import psutil
import time
import argparse
import curses
import signal
import sys
from collections import deque
from datetime import datetime, timedelta

class MemoryProfiler:
    def __init__(self, pid, update_interval=1.0):
        self.process = psutil.Process(pid)
        self.update_interval = update_interval
        self.memory_history = []
        self.time_history = []
        self.running = True
        
        # Set up signal handler for graceful exit
        signal.signal(signal.SIGINT, self.handle_interrupt)
        
    def handle_interrupt(self, signum, frame):
        self.running = False
        
    def get_memory_usage(self):
        """Get virtual memory usage in MB"""
        return self.process.memory_info().vms / (1024 * 1024)
    
    def format_duration(self, seconds):
        """Format duration in a human-readable way"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"

    def draw_line_graph(self, stdscr):
        height, width = stdscr.getmaxyx()
        graph_height = height - 4  # Leave room for headers and labels
        graph_width = width - 12   # Leave room for y-axis labels
        
        # Clear screen
        stdscr.clear()
        
        # Draw title
        title = f"Memory Usage for PID {self.process.pid} ({self.process.name()})"
        stdscr.addstr(0, 0, title[:width-1])
        
        if len(self.memory_history) > 1:
            # Calculate scaling factors
            max_mem = max(self.memory_history)
            min_mem = min(self.memory_history)
            mem_range = max_mem - min_mem
            if mem_range == 0:
                mem_range = 1  # Prevent division by zero
                
            # Draw y-axis labels and grid lines
            for i in range(graph_height):
                mem_value = max_mem - (i * mem_range / (graph_height - 1))
                label = f"{mem_value:.0f}MB"
                stdscr.addstr(i + 2, 0, label[:8].rjust(8))
                # Draw horizontal grid lines using dots
                stdscr.addstr(i + 2, 9, "·" * graph_width)
            
            # Draw vertical time axis labels
            total_duration = self.time_history[-1] - self.time_history[0]
            for x in range(5):  # Draw 5 time markers
                pos = x * graph_width // 4
                if pos < graph_width:
                    time_val = self.time_history[0] + (total_duration * x / 4)
                    label = self.format_duration(time_val)
                    if x > 0:  # Don't draw first vertical line over y-axis
                        # Draw vertical grid lines
                        for y in range(graph_height):
                            stdscr.addch(y + 2, pos + 9, "·")
                    try:
                        stdscr.addstr(height-1, pos + 9, label)
                    except curses.error:
                        pass  # Ignore if label doesn't fit
            
            # Draw the actual graph
            points = []
            if len(self.memory_history) > graph_width:
                # If we have more points than width, we need to compress
                chunk_size = len(self.memory_history) / graph_width
                for i in range(graph_width):
                    start_idx = int(i * chunk_size)
                    end_idx = int((i + 1) * chunk_size)
                    chunk = self.memory_history[start_idx:end_idx]
                    if chunk:
                        points.append(sum(chunk) / len(chunk))
            else:
                # If we have fewer points than width, use them directly
                points = self.memory_history

            # Draw the line graph using ASCII characters
            prev_y = None
            for x, mem in enumerate(points):
                if x < graph_width:
                    y_pos = int(2 + (max_mem - mem) * (graph_height - 1) / mem_range)
                    if 2 <= y_pos < height:
                        if prev_y is not None:
                            # Draw line between points using ASCII art
                            y_start = min(prev_y, y_pos)
                            y_end = max(prev_y, y_pos)
                            if y_start == y_end:
                                stdscr.addch(y_start, x + 9, "─")
                            else:
                                for y in range(y_start, y_end + 1):
                                    if y == y_start and y_start != y_end:
                                        stdscr.addch(y, x + 9, "╮" if prev_y < y_pos else "╭")
                                    elif y == y_end and y_start != y_end:
                                        stdscr.addch(y, x + 9, "╰" if prev_y < y_pos else "╯")
                                    elif y_start != y_end:
                                        stdscr.addch(y, x + 9, "│")
                        prev_y = y_pos
        
        # Draw current memory usage
        if self.memory_history:
            current_mem = self.memory_history[-1]
            duration = self.format_duration(self.time_history[-1])
            stdscr.addstr(height-2, 0, f"Current: {current_mem:.1f}MB  Duration: {duration}")
        
        stdscr.refresh()
    
    def run(self, stdscr):
        # Set up curses
        curses.curs_set(0)  # Hide cursor
        curses.use_default_colors()
        
        start_time = time.time()
        
        while self.running:
            try:
                current_memory = self.get_memory_usage()
                current_time = time.time() - start_time
                
                self.memory_history.append(current_memory)
                self.time_history.append(current_time)
                
                self.draw_line_graph(stdscr)
                
                time.sleep(self.update_interval)
                
            except psutil.NoSuchProcess:
                print(f"Process {self.process.pid} no longer exists.")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

def main():
    parser = argparse.ArgumentParser(description='Real-time memory usage profiler')
    parser.add_argument('pid', type=int, help='Process ID to monitor')
    parser.add_argument('-i', '--interval', type=float, default=1.0,
                        help='Update interval in seconds (default: 1.0)')
    
    args = parser.parse_args()
    
    try:
        profiler = MemoryProfiler(args.pid, args.interval)
        curses.wrapper(profiler.run)
    except psutil.NoSuchProcess:
        print(f"Error: Process {args.pid} not found")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()
