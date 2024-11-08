import { getNeighbors } from '../../services/GraphQuery';
import { NeoNode, NeoRelationship, UserCredentials } from '../../types';
import { graphLabels } from '../../utils/Constants';

export const handleGraphNodeClick = async (
  userCredentials: UserCredentials,
  elementId: string,
  viewMode: string,
  setNeoNodes: React.Dispatch<React.SetStateAction<NeoNode[]>>,
  setNeoRels: React.Dispatch<React.SetStateAction<NeoRelationship[]>>,
) => {
  try {
    const result = await getNeighbors(userCredentials, elementId);
    if (result && result.data.data.nodes.length > 0) {
      let { nodes } = result.data.data;
      if (viewMode === graphLabels.chatInfoView) {
        nodes = nodes.filter((node: NeoNode) => node.labels.length === 1 && node.properties.id !== null);
      }
      const nodeIds = new Set(nodes.map((node: NeoNode) => node.element_id));
      const relationships = result.data.data.relationships.filter(
        (rel: NeoRelationship) => nodeIds.has(rel.end_node_element_id) && nodeIds.has(rel.start_node_element_id)
      );
      setNeoNodes(nodes);
      setNeoRels(relationships);
    }
  } catch (error: any) {
    console.error('Error fetching neighbors:', error);
  }
};
