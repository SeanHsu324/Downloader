import numpy as np
from collections import Counter
from big_two_core_wrapper import evaluate_hand_c, compare_hands_c, HandEvaluation

# 重新定義常量
DECK_SIZE = 52
NUM_RANKS = 13
NUM_SUITS = 4

# 牌型定義
HAND_TYPES = {
    'PASS': 0, 'SINGLE': 1, 'PAIR': 2, 'TRIPLE': 3, 'STRAIGHT': 4,
    'FLUSH': 5, 'FULL_HOUSE': 6, 'FOUR_OF_A_KIND': 7, 'STRAIGHT_FLUSH': 8
}

# --- 輔助函式 (保留 Python 版本，因為它們很簡單且在 C 核心中未使用) ---

def get_rank(card_index):
    """從 0-51 索引獲取點數索引 (0-12)"""
    return card_index % NUM_RANKS

def get_suit(card_index):
    """從 0-51 索引獲取花色索引 (0-3)"""
    return card_index // NUM_RANKS

def get_card_value(card_index):
    """獲取牌的數值，用於比較大小 (點數優先，花色次之)"""
    rank = get_rank(card_index)
    suit = get_suit(card_index)
    # 數值: rank * 4 + suit
    return rank * NUM_SUITS + suit

def get_hand_vector(hand_indices):
    """將手牌索引列表轉換為 52 維 one-hot 向量"""
    vector = np.zeros(DECK_SIZE, dtype=np.int8)
    if hand_indices is not None:
        vector[hand_indices] = 1
    return vector

def get_hand_indices(hand_vector):
    """將 52 維 one-hot 向量轉換為手牌索引列表"""
    hand_vector = np.atleast_1d(hand_vector)
    return np.where(hand_vector == 1)[0].tolist()

# --- 牌型判斷 (C 語言接口) ---

def evaluate_hand_np(hand_vector):
    """
    使用 C 語言核心評估手牌。
    回傳: (牌型代碼, 牌型大小值)
    """
    if isinstance(hand_vector, tuple):
        hand_vector = np.array(hand_vector)
    # 確保 hand_vector 是 int8 類型，符合 C 語言接口
    hand_vector = hand_vector.astype(np.int8)
    
    # 調用 C 語言函數
    eval_result = evaluate_hand_c(hand_vector)
    
    # HandEvaluation 結構體包含 type 和 value
    return eval_result.type, eval_result.value

def compare_hands_np(hand1_vector, hand2_vector) -> int:
    """
    使用 C 語言核心比較兩手牌的大小。
    回傳: 1 (hand1 > hand2), 0 (hand1 == hand2 或牌型不符), -1 (hand1 < hand2)
    """
    if isinstance(hand1_vector, tuple):
        hand1_vector = np.array(hand1_vector)
    if isinstance(hand2_vector, tuple):
        hand2_vector = np.array(hand2_vector)
    # 確保 hand_vector 是 int8 類型，符合 C 語言接口
    hand1_vector = hand1_vector.astype(np.int8)
    hand2_vector = hand2_vector.astype(np.int8)
    
    # 調用 C 語言函數
    return compare_hands_c(hand1_vector, hand2_vector)

# --- 遊戲核心 (使用 C 語言核心邏輯) ---

class BigTwoGameNP:
    # 類的其他方法保持不變，因為它們只調用 evaluate_hand_np 和 compare_hands_np
    # 這些方法現在已經被 C 語言實現所替換
    
    def __init__(self, num_players=4):
        self.num_players = num_players
        self.hands = [] # 每個玩家的手牌 (52維 one-hot 向量)
        self.current_player = 0
        self.last_played_hand = None # 最後出的牌 (52維 one-hot 向量)
        self.last_played_player = -1
        self.players_passed = 0
        self.is_game_over = False
        
    def reset(self):
        """重置遊戲，發牌"""
        deck = np.arange(DECK_SIZE)
        np.random.shuffle(deck)
        
        self.hands = []
        for i in range(self.num_players):
            # 確保手牌是排序的 (雖然對 one-hot 向量無影響，但方便調試)
            hand_indices = np.sort(deck[i::self.num_players])
            self.hands.append(get_hand_vector(hand_indices))
            
        # 找出梅花 3 (索引 0) 的玩家
        start_player = -1
        for i, hand_vector in enumerate(self.hands):
            if hand_vector[0] == 1:
                start_player = i
                break
        
        self.current_player = start_player
        self.last_played_hand = get_hand_vector(None) # 使用空向量表示 None
        self.last_played_player = -1
        self.players_passed = 0
        self.is_game_over = False
        
        return self._get_state()

    def _get_state(self):
        """獲取當前遊戲狀態"""
        return {
            'current_player': self.current_player,
            'hands': self.hands,
            'last_played_hand': self.last_played_hand,
            'last_played_player': self.last_played_player,
            'players_passed': self.players_passed,
            'is_game_over': self.is_game_over,
            'is_start_of_game': self.is_start_of_game() # 確保這行存在
        }

    def is_start_of_game(self):
        """檢查是否為遊戲開始 (梅花 3 必須在牌中)"""
        # 牌桌為空，且當前玩家手牌中有梅花 3 (索引 0)
        return np.sum(self.last_played_hand) == 0 and self.hands[self.current_player][0] == 1

    def step(self, action_vector):
        """
        執行一個動作。
        action_vector: 52 維 one-hot 向量 (出牌)
        回傳: (new_state_dict, reward, done, info)
        """
        reward = 0.0
        terminated = False
        truncated = False
        info = {'is_legal': True}
        
        current_hand_vector = self.hands[self.current_player]
        
        # 1. 檢查是否為 Pass (空向量)
        is_pass = np.sum(action_vector) == 0
        
        if is_pass:
            # Pass
            if np.sum(self.last_played_hand) == 0:
                # 牌桌為空時不能 Pass
                reward = -10.0 # 懲罰非法 Pass
                terminated = True
                info['is_legal'] = False
                info['reason'] = 'Illegal Pass: Table is empty'
            else:
                self.players_passed += 1
                
        else:
            # 2. 檢查動作是否在手牌中 (action_vector <= current_hand_vector)
            if np.any(action_vector > current_hand_vector):
                # 出牌不在手牌中 (非法動作)
                reward = -10.0
                terminated = True
                info['is_legal'] = False
                info['reason'] = 'Illegal action: Card not in hand'
                
            # 3. 檢查是否為遊戲開始 (梅花 3 必須在牌中)
            elif np.sum(self.last_played_hand) == 0 and self.is_start_of_game() and action_vector[0] == 0:
                # 遊戲開始，但沒有出梅花 3
                reward = -10.0
                terminated = True
                info['is_legal'] = False
                info['reason'] = 'Illegal action: Must play 3C'
                
            # 4. 檢查是否大於最後出的牌
            elif np.sum(self.last_played_hand) > 0:
                # 使用 C 語言核心比較
                compare_result = compare_hands_np(action_vector, self.last_played_hand)
                if compare_result <= 0:
                    # 牌型不符或牌太小
                    reward = -10.0
                    terminated = True
                    info['is_legal'] = False
                    info['reason'] = 'Illegal action: Hand too small or type mismatch'
                else:
                    # 合法出牌
                    self.hands[self.current_player] -= action_vector
                    self.last_played_hand = action_vector
                    self.last_played_player = self.current_player
                    self.players_passed = 0
            
            else:
                # 牌桌為空，且是合法出牌 (非 Pass, 非遊戲開始強制 3C)
                self.hands[self.current_player] -= action_vector
                self.last_played_hand = action_vector
                self.last_played_player = self.current_player
                self.players_passed = 0
        
        # 5. 檢查遊戲是否結束
        if np.sum(self.hands[self.current_player]) == 0:
            self.is_game_over = True
            terminated = True
            reward = 100.0 # 勝利獎勵
            
        # 6. 處理連續 Pass
        if self.players_passed == self.num_players - 1 and np.sum(self.last_played_hand) > 0:
            # 所有其他玩家都 Pass，重置牌桌
            self.last_played_hand = get_hand_vector(None)
            self.last_played_player = -1
            self.players_passed = 0
            
        # 7. 輪到下一位玩家
        if not terminated:
            self.current_player = (self.current_player + 1) % self.num_players
            
        # 8. 遊戲結束時給予其他玩家懲罰
        if terminated and np.sum(self.hands[self.current_player]) == 0:
            # 只有在當前玩家贏了才計算懲罰
            remaining_cards = [np.sum(h) for h in self.hands]
            for i in range(self.num_players):
                if i != self.current_player:
                    # 懲罰與剩餘牌數成正比
                    reward -= remaining_cards[i] * 10
            
        return self._get_state(), reward, terminated, truncated, info

# --- 測試 ---
if __name__ == '__main__':
    # 測試 C 核心接口
    hand1_vector = np.zeros(DECK_SIZE, dtype=np.int8)
    hand1_vector[[0, 13, 26, 39, 51]] = 1 # 3C, 3D, 3H, 3S, 2S (鐵支)
    type, value = evaluate_hand_np(hand1_vector)
    print(f"鐵支牌型: {type}, 大小: {value}")
    
    hand2_vector = np.zeros(DECK_SIZE, dtype=np.int8)
    hand2_vector[[1, 14, 27, 40, 50]] = 1 # 4C, 4D, 4H, 4S, 2H (鐵支)
    type2, value2 = evaluate_hand_np(hand2_vector)
    print(f"鐵支牌型: {type2}, 大小: {value2}")
    
    compare_result = compare_hands_np(hand1_vector, hand2_vector)
    print(f"比較結果 (3鐵支 vs 4鐵支): {compare_result}") # 應該是 -1 (hand1 < hand2)
    
    # 測試遊戲步驟
    game = BigTwoGameNP()
    game.reset()
    print(f"起始玩家: {game.current_player}")
    
    # 找出梅花 3 (索引 0)
    start_player_hand = game.hands[game.current_player]
    
    # 嘗試出 3C
    action_vector = get_hand_vector([0])
    state, reward, terminated, truncated, info = game.step(action_vector)
    print(f"出牌: 3C, 下一玩家: {state['current_player']}, 獎勵: {reward}, 結束: {terminated}")
    
    # 嘗試 Pass
    state, reward, terminated, truncated, info = game.step(get_hand_vector(None))
    print(f"Pass, 下一玩家: {state['current_player']}, 獎勵: {reward}, 結束: {terminated}")
