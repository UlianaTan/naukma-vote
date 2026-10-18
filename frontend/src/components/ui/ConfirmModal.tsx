import React from 'react';
import { AlertTriangle, Lock, Trash2, X } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'danger' | 'primary';
  icon?: 'warning' | 'lock' | 'trash';
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = 'Підтвердити',
  cancelText = 'Скасувати',
  type = 'primary',
  icon = 'warning'
}: ConfirmModalProps) {
  if (!isOpen) return null;

  const isDanger = type === 'danger';

  const renderIcon = () => {
    switch (icon) {
      case 'lock':
        return <Lock className="w-6 h-6" />;
      case 'trash':
        return <Trash2 className="w-6 h-6" />;
      case 'warning':
      default:
        return <AlertTriangle className="w-6 h-6" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl w-full max-w-md p-6 shadow-xl relative animate-in fade-in zoom-in duration-200">
        
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 transition-colors rounded-full hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Іконка */}
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
          isDanger ? 'bg-red-50 text-red-600' : 'bg-slate-100 text-slate-700'
        }`}>
          {renderIcon()}
        </div>

        {/* Текст */}
        <h3 className="text-xl font-bold text-slate-900 mb-2">
          {title}
        </h3>
        <p className="text-slate-500 mb-8 text-sm leading-relaxed">
          {description}
        </p>

        {/* Кнопки */}
        <div className="flex justify-end gap-3 w-full">
          <button 
            onClick={onClose}
            className="px-5 py-2.5 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            {cancelText}
          </button>
          <button 
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className={`px-5 py-2.5 rounded-lg text-sm font-medium text-white transition-colors shadow-sm ${
              isDanger 
                ? 'bg-red-600 hover:bg-red-700' 
                : 'bg-[#0B1B3D] hover:bg-slate-800'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}