import numpy as np
import torch
import random
from big_two_model import BigTwoA2C, STATE_DIM, ACTION_SPACE_SIZE

# --- 基礎 Agent 類 ---
class BaseAgent:
    def __init__(self, name="BaseAgent"):
        self.name = name

    def choose_action(self, state_vector: np.ndarray, legal_action_mask: np.ndarray) -> int:
        """
        根據當前狀態和合法動作遮罩選擇動作索引。
        
        Args:
            state_vector: 當前狀態的 NumPy 向量。
            legal_action_mask: 合法動作的 NumPy 遮罩 (1: 合法, 0: 非法)。
            
        Returns:
            選擇的動作索引 (int)。
        """
        raise NotImplementedError

# --- 隨機出牌 Agent ---
class RandomAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="RandomAgent")

    def choose_action(self, state_vector: np.ndarray, legal_action_mask: np.ndarray) -> int:
        """
        從所有合法動作中隨機選擇一個動作。
        """
        legal_indices = np.where(legal_action_mask == 1)[0]
        
        if len(legal_indices) == 0:
            # 這不應該發生，因為至少有一個 Pass 動作 (索引 0) 應該是合法的
            # 但作為安全措施，如果沒有合法動作，則返回 Pass (索引 0)
            return 0 
        
        # 隨機選擇一個合法動作的索引
        return random.choice(legal_indices)

# --- 模型 Agent (用於 Old Model 或其他固定模型) ---
class ModelAgent(BaseAgent):
    def __init__(self, model: BigTwoA2C, device: torch.device, name="ModelAgent"):
        super().__init__(name=name)
        self.model = model
        self.device = device
        self.model.eval() # 設置為評估模式

    def load_weights(self, state_dict):
        """載入新的模型權重"""
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def choose_action(self, state_vector: np.ndarray, legal_action_mask: np.ndarray) -> int:
        """
        使用 A2C 模型以貪婪策略選擇動作。
        """
        state_tensor = torch.from_numpy(state_vector).float().unsqueeze(0).to(self.device)
        legal_mask_tensor = torch.from_numpy(legal_action_mask).float().unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            policy_logits, _ = self.model(state_tensor)
            
        # 應用遮罩：將非法動作的 logits 設置為極小值
        masked_logits = policy_logits + (legal_mask_tensor - 1) * 1e9
        
        # 選擇最大機率的動作 (貪婪策略)
        action_index = torch.argmax(masked_logits, dim=1).item()
        
        return action_index

# --- 輔助函式：創建對手 Agent 列表 ---
def create_opponent_agents(agent_type: str, model: BigTwoA2C = None, device: torch.device = None):
    """
    根據指定的類型創建三個對手 Agent (P1, P2, P3)。
    
    Args:
        agent_type: 'random' 或 'model'。
        model: 僅在 agent_type 為 'model' 時需要。
        device: 僅在 agent_type 為 'model' 時需要。
        
    Returns:
        包含三個 BaseAgent 實例的列表。
    """
    if agent_type == 'random':
        return [RandomAgent() for _ in range(3)]
    elif agent_type == 'model':
        if model is None or device is None:
            raise ValueError("Model and device must be provided for 'model' agent type.")
        # 讓三個對手都使用同一個模型實例
        return [ModelAgent(model, device, name=f"ModelAgent_P{i+1}") for i in range(3)]
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")
