import os
import sys
import time
import random
import select

# 1. 게임 설정
BOARD_WIDTH = 10
BOARD_HEIGHT = 20

# 2. 테트리스 7가지 블록 정의
SHAPES = [
    [[1, 1, 1, 1]],          # I (0)
    [[1, 1, 1], [0, 1, 0]],  # T (1)
    [[1, 1, 1], [1, 0, 0]],  # L (2)
    [[1, 1, 1], [0, 0, 1]],  # J (3)
    [[1, 1], [1, 1]],        # O (4)
    [[1, 1, 0], [0, 1, 1]],  # Z (5)
    [[0, 1, 1], [1, 1, 0]]   # S (6)
]

SHAPE_NAMES = ["I-MINO", "T-MINO", "L-MINO", "J-MINO", "O-MINO", "Z-MINO", "S-MINO"]

# 3. 공식 가이드라인 SRS (Super Rotation System) 킥 데이터 (y축 반전 완벽 반영)
SRS_KICKS_NORMAL = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0,  2), (-1,  2)], 
    (1, 0): [(0, 0), ( 1, 0), ( 1,  1), (0, -2), ( 1, -2)], 
    (1, 2): [(0, 0), ( 1, 0), ( 1,  1), (0, -2), ( 1, -2)], 
    (2, 1): [(0, 0), (-1, 0), (-1, -1), (0,  2), (-1,  2)], 
    (2, 3): [(0, 0), ( 1, 0), ( 1, -1), (0,  2), ( 1,  2)], 
    (3, 2): [(0, 0), (-1, 0), (-1,  1), (0, -2), (-1, -2)], 
    (3, 0): [(0, 0), (-1, 0), (-1,  1), (0, -2), (-1, -2)], 
    (0, 3): [(0, 0), ( 1, 0), ( 1, -1), (0,  2), ( 1,  2)]  
}

SRS_KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), ( 1, 0), (-2,  1), ( 1, -2)],
    (1, 0): [(0, 0), ( 2, 0), (-1, 0), ( 2, -1), (-1,  2)],
    (1, 2): [(0, 0), (-1, 0), ( 2, 0), (-1, -2), ( 2,  1)],
    (2, 1): [(0, 0), ( 1, 0), (-2, 0), ( 1,  2), (-2, -1)],
    (2, 3): [(0, 0), ( 2, 0), (-1, 0), ( 2, -1), (-1,  2)],
    (3, 2): [(0, 0), (-2, 0), ( 1, 0), (-2,  1), ( 1, -2)],
    (3, 0): [(0, 0), ( 1, 0), (-2, 0), ( 1,  2), (-2, -1)],
    (0, 3): [(0, 0), (-1, 0), ( 2, 0), (-1, -2), ( 2,  1)]
}

class Tetris:
    def __init__(self):
        self.board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.score = 0
        self.lines_cleared_total = 0
        self.game_over = False
        self.spin_message = ""
        
        self.hold_shape_idx = None  
        self.can_hold = True        
        
        self.bag = []
        self.refill_bag()
        
        self.current_shape_idx = self.bag.pop(0)
        self.current_piece = SHAPES[self.current_shape_idx]
        self.rotation_state = 0
        
        self.next_pieces = [self.bag.pop(0) for _ in range(5)]
        self.reset_piece_position()

    def refill_bag(self):
        new_bag = list(range(len(SHAPES)))
        random.shuffle(new_bag)
        self.bag.extend(new_bag)

    def reset_piece_position(self):
        self.piece_x = BOARD_WIDTH // 2 - len(self.current_piece[0]) // 2
        self.piece_y = 0
        self.rotation_state = 0
        if self.check_collision(self.current_piece, self.piece_x, self.piece_y):
            self.game_over = True

    def get_next_from_bag(self):
        if len(self.bag) < 7:
            self.refill_bag()
        return self.bag.pop(0)

    def check_collision(self, piece, nx, ny):
        for r, row in enumerate(piece):
            for c, val in enumerate(row):
                if val:
                    if (nx + c < 0 or nx + c >= BOARD_WIDTH or 
                        ny + r >= BOARD_HEIGHT or 
                        (ny + r >= 0 and self.board[ny + r][nx + c])):
                        return True
        return False

    def merge_piece(self):
        for r, row in enumerate(self.current_piece):
            for c, val in enumerate