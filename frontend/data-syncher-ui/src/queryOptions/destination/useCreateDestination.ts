import ServerRoutes from "@/constants/server-routes";
import AxiosInstance from "@/lib/axios/api-client";
import { type Destination } from "@/types/destination";
import { type ErrorResponseType } from "@/types/error";

import { useMutation, useQueryClient } from "@tanstack/react-query";

interface CreateDestinationResponse {
  message?: string;
  auth_url?: string;
}

const createDestination = async (
  payload: Destination | FormData,
): Promise<CreateDestinationResponse> => {
  const { data } = await AxiosInstance.post<CreateDestinationResponse>(
    ServerRoutes.destination.createDestination(),
    payload,
  );
  return data;
};

export default function useCreateDestination() {
  const queryClient = useQueryClient();
  return useMutation<
    CreateDestinationResponse,
    ErrorResponseType,
    Destination | FormData
  >({
    mutationFn: createDestination,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["destinations", "allUserCreatedDestinationList"],
      });
    },
  });
}
