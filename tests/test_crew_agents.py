import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys

# Add src to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.crew_agents import LifeOSAgents

class TestLifeOSAgents(unittest.TestCase):

    def setUp(self):
        # Sample configuration data
        self.sample_config = {
            'agent1': {
                'role': 'Role 1',
                'goal': 'Goal 1',
                'backstory': 'Backstory 1',
                'public': True,
                'tools': ['tool1'],
                'execution_mode': 'crew',
                'verbose': True,
                'allow_delegation': True
            },
            'agent2': {
                'role': 'Role 2',
                'goal': 'Goal 2',
                'backstory': 'Backstory 2',
                'public': False,
                'tools': ['tool_dict'],
                'execution_mode': 'fast',
                'model_name': 'fast-model'
            },
            'agent3': {
                 'role': 'Role 3',
                 'goal': 'Goal 3',
                 'backstory': 'Backstory 3',
                 'tools': ['missing_tool'],
                 'execution_mode': 'crew'
            }
        }
        
        # Mock TOOL_MAPPING
        self.mock_tool_instance = MagicMock()
        self.mock_tool_dict = {'subtool1': MagicMock(), 'subtool2': MagicMock()}
        
        self.tool_mapping_patcher = patch('src.crew_agents.TOOL_MAPPING', {
            'tool1': self.mock_tool_instance,
            'tool_dict': self.mock_tool_dict
        })
        self.mock_tool_mapping = self.tool_mapping_patcher.start()

        # Patch os.path.exists to always return True for config path
        self.exists_patcher = patch('os.path.exists', return_value=True)
        self.mock_exists = self.exists_patcher.start()

        # Patch yaml.safe_load
        self.yaml_patcher = patch('yaml.safe_load', return_value=self.sample_config)
        self.mock_yaml_load = self.yaml_patcher.start()
        
        # Patch open
        self.open_patcher = patch('builtins.open', mock_open(read_data="data"))
        self.mock_open = self.open_patcher.start()

    def tearDown(self):
        self.tool_mapping_patcher.stop()
        self.exists_patcher.stop()
        self.yaml_patcher.stop()
        self.open_patcher.stop()

    def test_init_loads_config(self):
        """Test that initialization loads the configuration."""
        agents_factory = LifeOSAgents()
        self.assertEqual(agents_factory.config, self.sample_config)
        self.mock_open.assert_called()
        self.mock_yaml_load.assert_called()

    def test_load_config_file_not_found(self):
        """Test that FileNotFoundError is raised if config file does not exist."""
        self.mock_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            LifeOSAgents()

    def test_get_agents_summary(self):
        """Test summary generation for public agents."""
        agents_factory = LifeOSAgents()
        summary = agents_factory.get_agents_summary()
        self.assertIn("AGENT1: Goal 1", summary)
        self.assertNotIn("AGENT2", summary) # agent2 is not public

    @patch('src.crew_agents.Agent')
    @patch('src.crew_agents.llm')
    def test_create_agent_crew_mode(self, mock_llm, mock_agent_class):
        """Test creation of a standard CrewAI agent."""
        agents_factory = LifeOSAgents()
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        agent = agents_factory.create_agent('agent1')

        self.assertEqual(agent, mock_agent_instance)
        mock_agent_class.assert_called_once()
        _, kwargs = mock_agent_class.call_args
        self.assertEqual(kwargs['role'], 'Role 1')
        self.assertEqual(kwargs['goal'], 'Goal 1')
        self.assertEqual(kwargs['backstory'], 'Backstory 1')
        self.assertEqual(kwargs['tools'], [self.mock_tool_instance])
        self.assertEqual(kwargs['llm'], mock_llm)
        self.assertTrue(kwargs['verbose'])
        self.assertTrue(kwargs['allow_delegation'])

    @patch('src.crew_agents.FastTrackAgent')
    @patch('src.crew_agents.llm')
    def test_create_agent_fast_mode(self, mock_llm, mock_fast_agent_class):
        """Test creation of a FastTrackAgent."""
        agents_factory = LifeOSAgents()
        mock_fast_instance = MagicMock()
        mock_fast_agent_class.return_value = mock_fast_instance

        agent = agents_factory.create_agent('agent2')

        self.assertEqual(agent, mock_fast_instance)
        mock_fast_agent_class.assert_called_once()
        _, kwargs = mock_fast_agent_class.call_args
        self.assertEqual(kwargs['role'], 'Role 2')
        # Check that dictionary tools were flattened
        self.assertIn(list(self.mock_tool_dict.values())[0], kwargs['tools'])
        self.assertIn(list(self.mock_tool_dict.values())[1], kwargs['tools'])
        self.assertEqual(kwargs['model_name'], 'fast-model')

    def test_create_agent_not_found(self):
        """Test that create_agent returns None for non-existent agent."""
        agents_factory = LifeOSAgents()
        agent = agents_factory.create_agent('non_existent_agent')
        self.assertIsNone(agent)

    @patch('src.crew_agents.Agent')
    @patch('src.crew_agents.logger')
    def test_create_agent_missing_tool_warning(self, mock_logger, mock_agent_class):
        """Test that a warning is logged when a tool is missing."""
        agents_factory = LifeOSAgents()
        agents_factory.create_agent('agent3')
        
        mock_logger.warning.assert_called()
        # Check if the specific warning about missing tool was called
        # We need to check call args, one of them should contain the tool name
        found_warning = False
        for call in mock_logger.warning.call_args_list:
            if 'missing_tool' in str(call):
                found_warning = True
                break
        self.assertTrue(found_warning, "Warning for missing tool not found")

if __name__ == '__main__':
    unittest.main()
