import torch
import torch.nn as nn
import torch.nn.functional as F
from action_space import ACTION_SPACE_SIZE
import numpy as np

# 狀態維度 (52+52+3+4+1+1 = 113)
STATE_DIM = 113
# 動作空間維度 (Pass + 4550 個固定動作 = 4551)
# ACTION_SPACE_SIZE 從 action_space.py 導入

class BigTwoA2C(nn.Module):
    """
    基於 A2C 的大老二決策 AI 模型 (NumPy 向量化版本)。
    包含一個共享特徵提取網路，以及 Actor (Policy) 和 Critic (Value) 兩個頭部。
    """
    def __init__(self, action_space_size=ACTION_SPACE_SIZE):
        super(BigTwoA2C, self).__init__()
        
        self.action_space_size = action_space_size
        
        # 共享基礎網路 (2 層 FC, 256 節點, ReLU)
        self.shared_layer_1 = nn.Linear(STATE_DIM, 256)
        self.shared_layer_2 = nn.Linear(256, 256)
        
        # Actor 網路 (Policy Head)
        self.actor_head = nn.Linear(256, self.action_space_size)
        
        # Critic 網路 (Value Head)
        self.critic_head = nn.Linear(256, 1)

    def forward(self, x):
        """
        前向傳播。
        x: 狀態向量 (Batch_size, STATE_DIM)
        回傳: 動作機率分佈 (logits), 狀態價值 V(S)
        """
        # 共享特徵提取
        x = F.relu(self.shared_layer_1(x))
        shared_features = F.relu(self.shared_layer_2(x))
        
        # Actor 輸出 (Logits)
        # 這裡輸出的是 Logits，Softmax 將在訓練流程中應用，以便於計算交叉熵損失。
        action_logits = self.actor_head(shared_features)
        
        # Critic 輸出 (狀態價值 V(S))
        value = self.critic_head(shared_features)
        
        return action_logits, value

    def get_action(self, state, legal_action_mask, device='cpu'):
        """
        根據狀態和合法動作遮罩，選擇一個動作。
        state: 單個狀態向量 (STATE_DIM)
        legal_action_mask: 合法動作遮罩 (ACTION_SPACE_SIZE)
        回傳: 選擇的動作索引 (int), 動作的 Log Probability (float), 狀態價值 V(S) (float)
        """
        # 將狀態轉換為 PyTorch Tensor
        state_tensor = torch.from_numpy(state).float().unsqueeze(0).to(device)
        
        # 前向傳播
        action_logits, value = self.forward(state_tensor)
        
        # 應用合法動作遮罩
        # 將非法動作的 Logits 設為極小值 (-inf)，這樣 Softmax 後機率會趨近於 0
        mask_tensor = torch.from_numpy(legal_action_mask).float().unsqueeze(0).to(device)
        # 這裡使用一個較大的負數來確保非法動作的機率為 0
        masked_logits = action_logits + (mask_tensor - 1) * 1e9
        
        # 動作機率分佈
        action_probs = F.softmax(masked_logits, dim=-1)
        
        # 根據機率分佈採樣動作
        dist = torch.distributions.Categorical(action_probs)
        action_index = dist.sample()
        
        # 計算 Log Probability
        log_prob = dist.log_prob(action_index)
        
        # 將 value 從 Tensor 轉換為 float
        value_float = value.squeeze().item()
        
        return action_index.item(), log_prob, value_float

# 測試模型架構
if __name__ == '__main__':
    model = BigTwoA2C()
    dummy_state = np.random.rand(STATE_DIM)
    dummy_mask = np.random.randint(0, 2, size=ACTION_SPACE_SIZE)
    action, log_prob, value = model.get_action(dummy_state, dummy_mask)
    print(f"Action Index: {action}, Log Prob: {log_prob}, Value: {value}")
    print(f"Model parameters count: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")
