import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface Column<T> {
  header: string;
  className?: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  isLoading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  selectedRowKey?: string | number;
  renderExpanded?: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  isLoading,
  emptyMessage = "No data.",
  onRowClick,
  selectedRowKey,
  renderExpanded,
}: DataTableProps<T>) {
  const colSpan = columns.length;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-[#A0AEC0]">
          <tr>
            {columns.map((col) => (
              <th key={col.header} className={cn("px-4 py-3", col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={colSpan} className="px-4 py-8 text-center text-[#A0AEC0]">
                Loading…
              </td>
            </tr>
          )}
          {!isLoading && rows.length === 0 && (
            <tr>
              <td colSpan={colSpan} className="px-4 py-8 text-center text-[#A0AEC0]">
                {emptyMessage}
              </td>
            </tr>
          )}
          {!isLoading &&
            rows.map((row) => {
              const key = rowKey(row);
              const isSelected = selectedRowKey !== undefined && key === selectedRowKey;
              return (
                <Fragment key={key}>
                  <tr
                    className={cn(
                      "border-t border-gray-100 transition-colors hover:bg-gray-50",
                      onRowClick && "cursor-pointer",
                      isSelected && "bg-teal-50",
                    )}
                    onClick={() => onRowClick?.(row)}
                  >
                    {columns.map((col) => (
                      <td key={col.header} className={cn("px-4 py-3", col.className)}>
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                  {isSelected && renderExpanded && (
                    <tr className="border-t border-gray-100 lg:hidden">
                      <td colSpan={colSpan} className="p-0">
                        {renderExpanded(row)}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
        </tbody>
      </table>
    </div>
  );
}
