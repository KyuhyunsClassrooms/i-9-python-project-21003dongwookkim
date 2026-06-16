import os
import sys
import time
import random
import select

# 1. 게임 설정
BOARD_WIDTH = 10
BOARD_HEIGHT = 20

# 2. SRS 가이드라인 표준 고정 매트릭스
SHAPES = [
    # I-MINO
    [[0, 0, 0, 0],
     [1, 1, 1, 1],
     [0, 0, 0, 0],
     [0, 0, 0, 0]],
    # T-MINO
    [[0, 1, 0],
     [1, 1, 1],
     [0, 0, 0]],
    # L-MINO
    [[0, 0, 1],
     [1, 1, 1],
     [0, 0, 0]],
    # J-MINO
    [[1, 0, 0],
     [1, 1, 1],
     [0, 0, 0]],
    # O-MINO
    [[1, 1],
     [1, 1]],
    # Z-MINO
    [[1, 1, 0],
     [0, 1, 1],
     [0, 0, 0]],
    # S-MINO
    [[0, 1, 1],
     [1, 1, 0],
     [0, 0, 0]]
]

SHAPE_NAMES = ["I-MINO", "T-MINO", "L-MINO", "J-MINO", "O-MINO", "Z-MINO", "S-MINO"]

# 공식 SRS 월킥 데이터 테이블 (TST를 구멍 안으로 쑤셔넣는 5단계 오프셋 보정값 포함)
SRS_KICKS_NORMAL = {
    (0, 1): [(0, 0), (-1, 0), (-1, -1), (0,  2), (-1,  2)], 
    (1, 2): [(0, 0), ( 1, 0), ( 1,  1), (0, -2), ( 1, -2)], 
    (2, 3): [(0, 0), ( 1, 0), ( 1, -1), (0,  2), ( 1,  2)], 
    (3, 0): [(0, 0), (-1, 0), (-1,  1), (0, -2), (-1, -2)], 
    (0, 3): [(0, 0), ( 1, 0), ( 1, -1), (0,  2), ( 1,  2)], 
    (3, 2): [(0, 0), ( 1, 0), ( 1,  1), (0, -2), ( 1, -2)], 
    (2, 1): [(0, 0), (-1, 0), (-1, -1), (0,  2), (-1,  2)], 
    (1, 0): [(0, 0), (-1, 0), (-1,  1), (0, -2), (-1, -2)]  
}

SRS_KICKS_I = {
    (0, 1): [(0, 0), (-2, 0), ( 1, 0), (-2,  1), ( 1, -2)],
    (1, 2): [(0, 0), (-1, 0), ( 2, 0), (-1, -2), ( 2,  1)],
    (2, 3): [(0, 0), ( 2, 0), (-1, 0), ( 2, -1), (-1,  2)],
    (3, 0): [(0, 0), ( 1, 0), (-2, 0), ( 1,  2), (-2, -1)],
    (0, 3): [(0, 0), (-1, 0), ( 2, 0), (-1, -2), ( 2,  1)],
    (3, 2): [(0, 0), (-2, 0), ( 1, 0), (-2,  1), ( 1, -2)],
    (2, 1): [(0, 0), ( 1, 0), (-2, 0), ( 1,  2), (-2, -1)],
    (1, 0): [(0, 0), ( 2, 0), (-1, 0), ( 2, -1), (-1,  2)]
}

class Tetris:
    def __init__(self):
        self.board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.score = 0
        self.lines_cleared_total = 0
        self.game_over = False
        self.spin_message = ""
        self.countdown_message = ""
        
        # T-스핀 정밀 판정용 변수
        self.last_move_was_rotate = False
        self.is_t_spin = False
        self.is_t_spin_mini = False
        
        self.hold_shape_idx = None  
        self.can_hold = True        
        
        self.lock_delay_time = 0.5   
        self.lock_timer_start = None 
        
        self.bag = []
        self.refill_bag()
        
        self.current_shape_idx = self.bag.pop(0)
        self.current_piece = [row[:] for row in SHAPES[self.current_shape_idx]]
        self.rotation_state = 0
        
        self.next_pieces = [self.bag.pop(0) for _ in range(5)]
        self.reset_piece_position()

    def refill_bag(self):
        new_bag = list(range(len(SHAPES)))
        random.shuffle(new_bag)
        self.bag.extend(new_bag)

    def reset_piece_position(self):
        self.piece_x = BOARD_WIDTH // 2 - len(self.current_piece[0]) // 2
        self.piece_y = -1 if self.current_shape_idx == 0 else 0
        self.rotation_state = 0
        self.lock_timer_start = None 
        self.last_move_was_rotate = False
        self.is_t_spin = False
        self.is_t_spin_mini = False
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
                    if (nx + c < 0 or nx + c >= BOARD_WIDTH or ny + r >= BOARD_HEIGHT):
                        return True
                    if ny + r >= 0 and self.board[ny + r][nx + c]:
                        return True
        return False

    def is_on_ground(self):
        return self.check_collision(self.current_piece, self.piece_x, self.piece_y + 1)

    def refresh_lock_delay(self):
        if self.is_on_ground():
            self.lock_timer_start = time.time()

    def merge_piece(self):
        for r, row in enumerate(self.current_piece):
            for c, val in enumerate(row):
                if val and self.piece_y + r >= 0:
                    self.board[self.piece_y + r][self.piece_x + c] = 1

    def clear_lines(self):
        new_board = [row for row in self.board if not all(row)]
        lines_cleared = BOARD_HEIGHT - len(new_board)
        while len(new_board) < BOARD_HEIGHT:
            new_board.insert(0, [0] * BOARD_WIDTH)
        self.board = new_board
        
        # 💥 [업그레이드] T-스핀 및 T-스핀 트리플(TST) 점수 시스템 반영
        if lines_cleared > 0:
            if self.is_t_spin:
                if lines_cleared == 3:
                    self.spin_message = "✨✨ T-SPIN TRIPLE!!! ✨✨"
                    self.score += 1600
                elif lines_cleared == 2:
                    self.spin_message = "✨ T-SPIN DOUBLE! ✨"
                    self.score += 1200
                elif lines_cleared == 1:
                    self.spin_message = "⭐ T-SPIN SINGLE ⭐"
                    self.score += 800
            elif self.is_t_spin_mini:
                self.spin_message = f"🍃 T-SPIN MINI ({lines_cleared} Line) 🍃"
                self.score += 200 * lines_cleared
            else:
                # 일반 라인 클리어
                self.score += (lines_cleared ** 2) * 100
            
            self.lines_cleared_total += lines_cleared
        else:
            # 라인을 지우지 않은 순수 T-스핀 행동 점수
            if self.is_t_spin:
                self.spin_message = "🔮 T-SPIN 🔮"
                self.score += 400
            elif self.is_t_spin_mini:
                self.spin_message = "🍃 T-SPIN MINI 🍃"
                self.score += 100

    def rotate_matrix(self, matrix, clockwise=True):
        N = len(matrix)
        rotated = [[0] * N for _ in range(N)]
        for r in range(N):
            for c in range(N):
                if clockwise:
                    rotated[c][N - 1 - r] = matrix[r][c]
                else:
                    rotated[N - 1 - c][r] = matrix[r][c]
        return rotated

    def rotate_piece(self, clockwise=True):
        if self.current_shape_idx == 4: 
            return

        next_rotation = (self.rotation_state + 1) % 4 if clockwise else (self.rotation_state - 1) % 4
        rotated = self.rotate_matrix(self.current_piece, clockwise)
        
        # 1단계: 제자리 회전
        if not self.check_collision(rotated, self.piece_x, self.piece_y):
            self.current_piece = rotated
            self.rotation_state = next_rotation
            self.last_move_was_rotate = True
            self.check_t_spin_status(kick_used=False) # T-스핀 체크
            self.refresh_lock_delay()
            return

        # 2단계: SRS 월킥 연산 (TST를 만드는 결정적 5단계 루프)
        kick_table = SRS_KICKS_I if self.current_shape_idx == 0 else SRS_KICKS_NORMAL
        kicks = kick_table.get((self.rotation_state, next_rotation), [(0, 0)])
        
        for idx, (dx, dy) in enumerate(kicks):
            test_x = self.piece_x + dx
            test_y = self.piece_y - dy 
            
            if not self.check_collision(rotated, test_x, test_y):
                self.piece_x = test_x
                self.piece_y = test_y
                self.current_piece = rotated
                self.rotation_state = next_rotation
                self.last_move_was_rotate = True
                
                # TST는 주로 월킥 테이블의 마지막 킥(idx == 4)을 타고 들어갑니다.
                self.check_t_spin_status(kick_used=True, kick_index=idx)
                self.refresh_lock_delay()
                return

    def check_t_spin_status(self, kick_used=False, kick_index=0):
        """★ 테트리스 공식 룰: 3-Corner T-Spin 판정 알고리즘 ★"""
        if self.current_shape_idx != 1: # T-미노가 아니면 패스
            return
            
        # T-블록 중심 기준 4개의 대각선 모퉁이 좌표 설정
        cx, cy = self.piece_x + 1, self.piece_y + 1
        corners = [
            (cx - 1, cy - 1), # 좌상 (0)
            (cx + 1, cy - 1), # 우상 (1)
            (cx + 1, cy + 1), # 우하 (2)
            (cx - 1, cy + 1)  # 좌하 (3)
        ]
        
        # 각 코너가 벽이거나 블록으로 막혀있는지 카운트
        blocked = []
        for x, y in corners:
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                blocked.append(True)
            elif y >= 0 and self.board[y][x]:
                blocked.append(True)
            else:
                blocked.append(False)
                
        total_blocked = sum(blocked)
        
        # 공식 3-Corner Rule: 4칸 중 3칸 이상 막혀있어야 함
        if total_blocked >= 3:
            # T-블록이 바라보는 방향의 '앞쪽 두 모퉁이'가 막혔는지 확인하여 Mini와 정식 구분
            # 단, TST에 사용되는 대형 월킥(5번째 오프셋)을 타고 들어왔다면 무조건 정식 T-스핀으로 인정!
            if kick_used and kick_index == 4:
                self.is_t_spin = True
                self.is_t_spin_mini = False
            else:
                # 일반적인 회전 시 앞쪽 코너 판정
                # 회전 상태별 앞쪽 코너 인덱스 정의: 0(상), 1(우), 2(하), 3(좌)
                front_corners = {
                    0: (0, 1), # 좌상, 우상
                    1: (1, 2), # 우상, 우하
                    2: (2, 3), # 우하, 좌하
                    3: (3, 0)  # 좌하, 좌상
                }
                f1, f2 = front_corners[self.rotation_state]
                front_blocked_count = blocked[f1] + blocked[f2]
                
                if front_blocked_count == 2:
                    self.is_t_spin = True
                    self.is_t_spin_mini = False
                else:
                    self.is_t_spin_mini = True
                    self.is_t_spin = False
            
            # 텍스트 안내 피드백
            if self.is_t_spin:
                self.spin_message = "🔮 T-SPIN READY 🔮"
            elif self.is_t_spin_mini:
                self.spin_message = "🍃 T-SPIN MINI READY 🍃"
        else:
            self.is_t_spin = False
            self.is_t_spin_mini = False

    def hold_piece(self):
        if not self.can_hold:
            return  
            
        if self.hold_shape_idx is None:
            self.hold_shape_idx = self.current_shape_idx
            self.current_shape_idx = self.next_pieces.pop(0)
            self.next_pieces.append(self.get_next_from_bag())
        else:
            temp = self.hold_shape_idx
            self.hold_shape_idx = self.current_shape_idx
            self.current_shape_idx = temp
            
        self.current_piece = [row[:] for row in SHAPES[self.current_shape_idx]]
        self.reset_piece_position()
        self.can_hold = False
        self.spin_message = ""

    def hard_drop(self):
        while not self.check_collision(self.current_piece, self.piece_x, self.piece_y + 1):
            self.piece_y += 1
            self.score += 2
            self.last_move_was_rotate = False # 수직 이동했으므로 플래그 초기화되나, 하드드롭 직전 상태 유지
        self.lock_piece_and_next()

    def lock_piece_and_next(self):
        # 고정 직전에 마지막 행동이 회전이었고 T-스핀 조건이 만족된 경우 최종 T-스핀 판정 확정
        if not self.last_move_was_rotate:
            self.is_t_spin = False
            self.is_t_spin_mini = False
            
        self.merge_piece()
        self.clear_lines()
        
        self.can_hold = True
        self.current_shape_idx = self.next_pieces.pop(0)
        self.current_piece = [row[:] for row in SHAPES[self.current_shape_idx]]
        self.next_pieces.append(self.get_next_from_bag())
        
        self.reset_piece_position()

    def move(self, dx, dy):
        if not self.check_collision(self.current_piece, self.piece_x + dx, self.piece_y + dy):
            self.piece_x += dx
            self.piece_y += dy
            if dx != 0 or dy != 0:
                self.spin_message = ""
                self.last_move_was_rotate = False # 이동 시 회전 플래그 해제
                self.is_t_spin = False
                self.is_t_spin_mini = False
                self.refresh_lock_delay() 
            return True
        
        if dy > 0:
            if self.lock_timer_start is None:
                self.lock_timer_start = time.time()
        return False

    def update_lock_delay_logic(self):
        if self.is_on_ground():
            if self.lock_timer_start is None:
                self.lock_timer_start = time.time()
            elif time.time() - self.lock_timer_start >= self.lock_delay_time:
                self.lock_piece_and_next()
        else:
            self.lock_timer_start = None

    def draw(self):
        sys.stdout.write("\033[H")
        
        output = []
        output.append("===================================\n")
        output.append("   T-SPIN TRIPLE (TST) VALIDATED   \n")
        output.append("===================================\n")
        
        hold_name = SHAPE_NAMES[self.hold_shape_idx].split('-')[0] if self.hold_shape_idx is not None else "NONE"
        output.append(f" SCORE: {self.score:<6} | LINES: {self.lines_cleared_total:<3}\n")
        
        if self.countdown_message:
            output.append(f" HOLD : [{hold_name:<4}]  🔥 {self.countdown_message} 🔥\n")
        else:
            output.append(f" HOLD : [{hold_name:<4}] {self.spin_message}\n")
            
        output.append("+" + "---" * BOARD_WIDTH + "+  [NEXT]\n")

        display_board = [row[:] for row in self.board]
        if not self.countdown_message:
            for r, row in enumerate(self.current_piece):
                for c, val in enumerate(row):
                    if val and (self.piece_y + r) >= 0 and (self.piece_y + r) < BOARD_HEIGHT:
                        display_board[self.piece_y + r][self.piece_x + c] = 2

        next_lines = {i: "" for i in range(BOARD_HEIGHT)}
        for idx, p_idx in enumerate(self.next_pieces):
            name = SHAPE_NAMES[p_idx].split('-')[0]
            next_lines[idx * 2 + 1] = f"  {idx+1}: {name}"

        for i, row in enumerate(display_board):
            board_segment = "|"
            for val in row:
                if val == 0:   board_segment += " . "
                elif val == 1: board_segment += "[X]"
                elif val == 2: board_segment += "[O]"
            board_segment += "|"
            
            line = board_segment + next_lines[i] + "\n"
            output.append(line)
            
        output.append("+" + "---" * BOARD_WIDTH + "+\n")
        output.append(" [A]◀  [D]▶  [S]▼   [W]Rotate-R  [E]Rotate-L\n")
        output.append(" [C]Hold  [Space]HardDrop  [Q]Quit\n")
        
        sys.stdout.write("".join(output))
        sys.stdout.flush()

def get_input():
    if select.select([sys.stdin], [], [], 0.03)[0]:
        return sys.stdin.read(1)
    return None

def main():
    import tty
    import termios
    old_settings = termios.tcgetattr(sys.stdin)
    
    os.system('clear' if os.name != 'nt' else 'cls')
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        game = Tetris()
        
        countdown_steps = ["READY? 3", "READY? 2", "READY? 1", "READY GO!!!"]
        for step in countdown_steps:
            game.countdown_message = step
            game.draw()
            time.sleep(0.7)
            
        game.countdown_message = "" 
        
        last_drop_time = time.time()
        drop_interval = 0.45 

        while not game.game_over:
            game.draw()
            game.update_lock_delay_logic() 
            
            if time.time() - last_drop_time > drop_interval:
                game.move(0, 1)
                last_drop_time = time.time()
            
            key = get_input()
            if key:
                if key != ' ':
                    key = key.lower()
                
                if key == 'a':     game.move(-1, 0)
                elif key == 'd':   game.move(1, 0)
                elif key == 's':   game.move(0, 1)
                elif key == 'w':   game.rotate_piece(clockwise=True)  
                elif key == 'e':   game.rotate_piece(clockwise=False) 
                elif key == 'c':   game.hold_piece() 
                elif key == ' ':   game.hard_drop()  
                elif key == 'q':   break
                    
            time.sleep(0.01) 
                    
        if game.game_over:
            game.draw()
            print("\n💀 GAME OVER 💀")
            print(f"최종 스코어: {game.score}")

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    main()