import { useState, useRef } from 'react';
import { LeftPanel } from './components/LeftPanel';
import { DataSelection } from './components/DataSelection';
import { InfoSearch } from './components/InfoSearch';
import { AIGeneration } from './components/AIGeneration';

export default function App() {
  const [selectedSection, setSelectedSection] = useState(0);
  const [selectedPressRelease, setSelectedPressRelease] = useState<string | null>(null);
  const [selectedReferences, setSelectedReferences] = useState<string[]>([]);
  const sectionRefs = [
    useRef<HTMLDivElement>(null),
    useRef<HTMLDivElement>(null),
    useRef<HTMLDivElement>(null)
  ];

  const handleSectionChange = (index: number) => {
    setSelectedSection(index);
    sectionRefs[index].current?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  };

  const handlePressReleaseSelect = (id: string) => {
    if (selectedPressRelease === id) {
      setSelectedPressRelease(null);
    } else {
      setSelectedPressRelease(id);
    }
    setSelectedReferences([]);
  };

  const handleRefresh = () => {
    setSelectedPressRelease(null);
    setSelectedReferences([]);
  };

  const handleGoToSearch = () => {
    handleSectionChange(1);
  };

  return (
    <div className="h-screen flex overflow-hidden bg-[#F5F5F0]">
      <LeftPanel
        selectedSection={selectedSection}
        onSelectSection={handleSectionChange}
      />

      <div
        className="flex-1 ml-[358px] overflow-y-auto scroll-smooth"
        style={{ scrollSnapType: 'y mandatory' }}
      >
        <div ref={sectionRefs[0]} style={{ scrollSnapAlign: 'start' }}>
          <DataSelection
            selectedId={selectedPressRelease}
            onSelect={handlePressReleaseSelect}
            onNext={handleGoToSearch}
            onRefresh={handleRefresh}
          />
        </div>
        <div ref={sectionRefs[1]} style={{ scrollSnapAlign: 'start' }}>
          <InfoSearch
            pressReleaseId={selectedPressRelease}
            selectedRefs={selectedReferences}
            onSelectRefs={setSelectedReferences}
          />
        </div>
        <div ref={sectionRefs[2]} style={{ scrollSnapAlign: 'start' }}>
          <AIGeneration
            pressReleaseId={selectedPressRelease}
            referenceIds={selectedReferences}
          />
        </div>
      </div>
    </div>
  );
}
